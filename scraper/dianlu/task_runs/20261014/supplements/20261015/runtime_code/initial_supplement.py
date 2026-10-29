"""Bounded supplemental crawl; the original archive and receipts stay immutable."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urljoin, urlparse

import httpx

from .config import DEFAULT_USER_AGENT
from .public_transport import public_transport
from .referenced_archive import safe_public_url, reference_key
from .robots_policy import RobotsPolicy
from .storage import read_json, write_json, append_jsonl, iter_jsonl

BASE = Path(__file__).resolve().parents[1] / 'task_runs/20261014'
ROOT = BASE / 'supplements/20261015'
RETRY = {429, 500, 502, 503, 504}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def atomic_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    write_json(temporary, data)
    temporary.replace(path)


def initialize(root=ROOT, base=BASE):
    for part in ('reports', 'data/assets', 'data/raw', 'research'):
        (root / part).mkdir(parents=True, exist_ok=True)
    state_path = root / 'reports/budget.json'
    state = read_json(state_path)
    if state:
        return state
    old = read_json(base / 'reports/resource_limits.json')
    diagnostic = read_json(base / 'reports/gap_investigation_20261015/investigation_summary.json')
    original_files = ['reports/resource_limits.json', 'reports/referenced_progress.json',
                      'reports/failed_references.csv', 'reports/pending_references.csv',
                      'data/processed/referenced_manifest.json', 'data/raw/referenced_attempts.jsonl',
                      'data/processed/projects.json', 'data/processed/articles.json',
                      'data/processed/schools.json', 'data/processed/dianedu.sqlite']
    original = {name: digest(base / name) for name in original_files}
    write_json(root / 'reports/original_integrity.json', original)
    for name in ('completion_acceptance.md', 'completion_audit.json'):
        (root / 'reports' / ('original_' + name)).write_bytes((base / 'reports' / name).read_bytes())
    state = dict(started_at=now(), deadline_epoch=time.time() + 4 * 3600,
                 stage_max_bytes=1_000_000_000, cumulative_max_bytes=20_000_000_000,
                 original_transferred_bytes=old['transferred_bytes'],
                 prior_diagnostic_bytes=diagnostic['diagnostic_response_bytes'],
                 search_transfer_reserve_bytes=10_000_000, network_response_bytes=0,
                 http_requests=0, max_http_requests=1500, status='prepared',
                 search_max_queries=192, article_max_candidate_pages=96)
    atomic_json(state_path, state)
    return state


def check_budget(state, at=None):
    charged = state['prior_diagnostic_bytes'] + state['search_transfer_reserve_bytes'] + state['network_response_bytes']
    if (at or time.time()) >= state['deadline_epoch']:
        raise RuntimeError('time_budget_reached')
    if charged >= state['stage_max_bytes'] or charged + state['original_transferred_bytes'] >= state['cumulative_max_bytes']:
        raise RuntimeError('byte_budget_reached')
    if state['http_requests'] >= state['max_http_requests']:
        raise RuntimeError('http_request_budget_reached')


def valid_asset(body, content_type):
    content_type = (content_type or '').split(';')[0].lower()
    if not body:
        return 'empty_payload'
    if 'html' in content_type or 'json' in content_type:
        return 'non_asset_payload'
    if content_type.startswith('image/'):
        magic = body.startswith((b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n', b'GIF87a', b'GIF89a', b'\x00\x00\x01\x00'))
        magic = magic or (body.startswith(b'RIFF') and body[8:12] == b'WEBP') or (content_type == 'image/svg+xml' and b'<svg' in body[:4096])
        if not magic:
            return 'image_signature_mismatch'
    return None


class SupplementalCrawler:
    def __init__(self, root=ROOT, base=BASE, transport=None):
        self.root, self.base = root, base
        self.state = initialize(root, base)
        self.last_request = 0.0
        self.policies = {}
        self.host_delays = {}
        self.blocked = set(read_json(base / 'reports/referenced_progress.json', {}).get('blocked_hosts', []))
        self.client = httpx.AsyncClient(transport=transport or public_transport(), trust_env=False,
            follow_redirects=False, timeout=httpx.Timeout(20, connect=10),
            headers={'User-Agent': DEFAULT_USER_AGENT, 'Accept-Encoding': 'identity'})
        self.receipts = {x['url']: x for x in iter_jsonl(root / 'data/raw/resource_attempts.jsonl')}

    def save_state(self):
        self.state['updated_at'] = now()
        self.state['processed_resources'] = len(self.receipts)
        self.state['saved_files'] = sum(bool(x.get('local_path')) for x in self.receipts.values())
        atomic_json(self.root / 'reports/budget.json', self.state)

    async def request(self, url, max_bytes=100_000_000):
        check_budget(self.state)
        if not safe_public_url(url):
            return {'error_type': 'excluded_access_or_host'}, b''
        host = urlparse(url).hostname
        if host in self.blocked:
            return {'error_type': 'host_access_denied_stop'}, b''
        delay = max(2, self.host_delays.get(host, 0))
        wait = max(0, delay - (time.monotonic() - self.last_request))
        if time.time() + wait >= self.state['deadline_epoch']:
            raise RuntimeError('time_budget_reached')
        await asyncio.sleep(wait)
        self.last_request = time.monotonic()
        self.client.cookies.clear()
        self.state['http_requests'] += 1
        self.save_state()
        row = {'url': url, 'requested_at': now()}
        body = bytearray()
        try:
            async with self.client.stream('GET', url) as response:
                row.update(status_code=response.status_code, content_type=response.headers.get('content-type'),
                           content_length=response.headers.get('content-length'), location=response.headers.get('location'),
                           retry_after=response.headers.get('retry-after'))
                if response.status_code in (401, 403):
                    self.blocked.add(host)
                if response.headers.get('content-encoding', 'identity') != 'identity':
                    row['error_type'] = 'unexpected_content_encoding'
                    return row, b''
                charged = self.state['prior_diagnostic_bytes'] + self.state['search_transfer_reserve_bytes'] + self.state['network_response_bytes']
                room = min(self.state['stage_max_bytes']-charged, self.state['cumulative_max_bytes']-self.state['original_transferred_bytes']-charged)
                limit = min(max_bytes, room-16384)
                if limit <= 0:
                    raise RuntimeError('byte_budget_reached')
                length = response.headers.get('content-length')
                if length and int(length) > limit and response.status_code == 200:
                    row['error_type'] = 'per_file_or_remaining_budget_limit'
                    return row, b''
                async for chunk in response.aiter_raw(chunk_size=16384):
                    self.state['network_response_bytes'] += len(chunk)
                    self.save_state()
                    check_budget(self.state)
                    body.extend(chunk)
                    if len(body) > limit or (response.status_code != 200 and len(body) > 16384):
                        row['error_type'] = 'response_size_limit'
                        break
        except httpx.HTTPError as exc:
            row['error_type'] = type(exc).__name__
        finally:
            row['response_bytes_read'] = len(body)
            row['response_sha256'] = hashlib.sha256(body).hexdigest()
            if b'<Code>' in body:
                row['origin_error_code'] = body.split(b'<Code>', 1)[1].split(b'</Code>', 1)[0].decode(errors='replace')[:100]
            append_jsonl(self.root / 'data/raw/http_attempts.jsonl', row)
        return row, bytes(body)

    async def allowed(self, url):
        parsed = urlparse(url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        if origin not in self.policies:
            robot_url = origin + '/robots.txt'
            chain = []
            for _ in range(5):
                row, body = await self.request(robot_url, 65536)
                chain.append(row)
                if row.get('error_type'):
                    policy = False
                    break
                status = row.get('status_code')
                if status in (301, 302, 303, 307, 308) and row.get('location'):
                    robot_url = urljoin(robot_url, row['location'])
                    continue
                if status == 404:
                    policy = True
                elif status == 200 and ('html' not in (row.get('content_type') or '').lower() or b'User-agent:' in body or b'User-Agent:' in body):
                    policy = RobotsPolicy(body.decode(errors='replace'), DEFAULT_USER_AGENT)
                    self.host_delays[parsed.hostname] = policy.delay
                else:
                    policy = False
                break
            else:
                policy = False
            self.policies[origin] = policy
            append_jsonl(self.root / 'data/raw/robots_receipts.jsonl', {'origin': origin, 'chain': chain,
                'policy': 'not_found' if policy is True else 'verified' if isinstance(policy, RobotsPolicy) else 'unavailable',
                'robots_text': body.decode(errors='replace')[:65536] if row.get('status_code') == 200 else None})
        policy = self.policies[origin]
        return policy is True or isinstance(policy, RobotsPolicy) and policy.can_fetch(url)

    async def download(self, item):
        current = item.get('historical_final_url') or item['url']
        row = dict(item, started_at=now(), url=item['url'])
        chain = []
        for _ in range(5):
            if not safe_public_url(current):
                return dict(row, error_type='excluded_access_or_host')
            if not await self.allowed(current):
                return dict(row, error_type='robots_disallowed_or_unavailable', chain=chain)
            reply, body = await self.request(current)
            chain.append(reply)
            row.update(final_url=current, status_code=reply.get('status_code'), content_type=reply.get('content_type'), chain=chain)
            if reply.get('error_type'):
                return dict(row, error_type=reply['error_type'])
            if reply.get('status_code') in (301, 302, 303, 307, 308) and reply.get('location'):
                current = urljoin(current, reply['location'])
                continue
            if reply.get('status_code') != 200:
                return dict(row, error_type=f"http_{reply.get('status_code')}")
            error = valid_asset(body, reply.get('content_type'))
            if error:
                return dict(row, error_type=error)
            # A redirect to a new site's HTML homepage is never an image recovery.
            suffix = Path(urlparse(current).path).suffix
            if not suffix or len(suffix) > 8:
                suffix = '.bin'
            path = self.root / 'data/assets' / (hashlib.sha256(item['url'].encode()).hexdigest() + suffix)
            if path.exists():
                return dict(row, error_type='existing_target_requires_receipt_reconciliation')
            temporary = path.with_suffix(path.suffix + '.part')
            temporary.write_bytes(body)
            temporary.replace(path)
            return dict(row, local_path=str(path.relative_to(self.root)), size_bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), completed_at=now())
        return dict(row, error_type='too_many_redirects')

    async def run(self, max_items=None):
        import csv
        with (self.base / 'reports/gap_investigation_20261015/resource_triage.csv').open(encoding='utf-8-sig', newline='') as f:
            targets = list(csv.DictReader(f))
        priority = {'public_recovery_candidate': 0, 'transient_network_failure': 1, 'site_moved_no_equivalent_asset': 2,
                    'policy_or_origin_unverified': 3, 'suspected_stale_or_missing': 4}
        selected = sorted([x for x in targets if x['category'] in priority], key=lambda x: priority[x['category']])
        self.state.update(status='running', resource_targets=len(selected))
        self.save_state()
        done = 0
        try:
            for item in selected:
                if item['url'] in self.receipts:
                    continue
                check_budget(self.state)
                for attempt in range(3):
                    record = await self.download(item)
                    record['attempt'] = attempt + 1
                    transient = record.get('error_type') in {'ConnectError','ConnectTimeout','ReadTimeout','ReadError','RemoteProtocolError'} or record.get('status_code') in RETRY
                    append_jsonl(self.root / 'data/raw/resource_attempts.jsonl', record)
                    self.receipts[item['url']] = record
                    self.save_state()
                    if not transient or attempt == 2:
                        break
                    retry_after = record.get('chain', [{}])[-1].get('retry_after')
                    pause = max(5 * (attempt + 1), float(retry_after) if retry_after and retry_after.isdigit() else 0)
                    if time.time() + pause >= self.state['deadline_epoch']:
                        raise RuntimeError('required_wait_exceeds_time_budget')
                    await asyncio.sleep(pause)
                done += 1
                if done % 20 == 0 or record.get('local_path'):
                    print(json.dumps({'processed':len(self.receipts),'saved':self.state['saved_files'],'network_bytes':self.state['network_response_bytes'],'requests':self.state['http_requests']}), flush=True)
                if max_items and done >= max_items:
                    self.state.update(status='pilot_finished')
                    break
            else:
                self.state.update(status='resource_queue_finished')
        except Exception as exc:
            self.state.update(status='stopped', stop_reason=str(exc))
            raise
        finally:
            atomic_json(self.root / 'reports/resource_manifest.json', list(self.receipts.values()))
            self.save_state()
            await self.client.aclose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pilot', type=int)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(initialize(), ensure_ascii=False))
    else:
        asyncio.run(SupplementalCrawler().run(args.pilot))


if __name__ == '__main__':
    main()
