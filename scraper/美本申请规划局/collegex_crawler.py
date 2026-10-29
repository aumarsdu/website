"""Archive the two public datasets used by CollegeX /activities. Standard library only."""
import argparse
import csv
import hashlib
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

ROOT = 'https://college-x.com'
ENDPOINTS = {'competitions': '/api/competitions', 'summer_programs': '/api/summer-programs'}
USER_AGENT = 'CollegeXPublicArchive/1.0 (authorized public activities archive)'


def parse_records(raw):
    records = json.loads(raw)
    if not isinstance(records, list):
        raise ValueError('Expected a JSON list')
    for item in records:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not item['name'].strip():
            raise ValueError('Each record must be an object with a nonempty name')
    return records


def canonical_url(url):
    if not url:
        return None
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in ('https', 'http') or not parts.hostname:
        raise ValueError('Invalid external URL')
    return urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or '/', parts.query, ''))


def digest(item):
    return hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def normalize(records, kind, source_url, timestamp):
    result, seen = [], set()
    for item in records:
        key = digest(item)
        if key in seen:
            continue
        seen.add(key)
        raw_url = item.get('website') if kind == 'competitions' else item.get('url')
        try:
            normalized_url = canonical_url(raw_url)
        except (ValueError, TypeError):
            normalized_url = None
        result.append({'record_id': kind + ':' + key[:20], 'activity_type': kind,
                       'source_url': source_url, 'source_page_url': ROOT + '/activities',
                       'crawled_at': timestamp, 'canonical_url': normalized_url, 'data': item})
    return result


def csv_content(records):
    fields = sorted({key for record in records for key in record['data']})
    meta = ['record_id', 'activity_type', 'source_url', 'source_page_url', 'crawled_at', 'canonical_url']
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=meta + fields)
    writer.writeheader()
    for record in records:
        writer.writerow({**{key: record[key] for key in meta}, **record['data']})
    return stream.getvalue()


class Fetcher:
    def __init__(self, args, directory):
        self.args, self.directory = args, directory
        self.last_request, self.requests = 0, 0
        self.manifest, self.errors = [], []

    def get(self, path, filename):
        url = ROOT + path
        for attempt in range(self.args.retries + 1):
            if self.requests >= self.args.max_pages:
                raise RuntimeError('max-pages hard cap reached')
            time.sleep(max(0, self.args.rate_limit - (time.monotonic() - self.last_request)))
            self.requests += 1
            self.last_request = time.monotonic()
            try:
                request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json,text/html,*/*'})
                with urllib.request.urlopen(request, timeout=self.args.timeout) as response:
                    if urllib.parse.urlsplit(response.url).netloc != 'college-x.com':
                        raise RuntimeError('Unexpected redirect host')
                    raw = response.read(10_000_001)
                    if len(raw) > 10_000_000:
                        raise RuntimeError('Response exceeds 10MB safety cap')
                    entry = {'url': url, 'status': response.status, 'fetched_at': datetime.now(timezone.utc).isoformat(),
                             'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'file': 'raw/' + filename}
                (self.directory / 'raw' / filename).write_bytes(raw)
                self.manifest.append(entry)
                print(json.dumps({'event': 'fetched', **entry}, ensure_ascii=False), flush=True)
                return raw
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
                code = getattr(error, 'code', None)
                category = ('http_' + str(code)) if code else 'network_or_timeout'
                self.errors.append({'url': url, 'category': category, 'attempt': attempt + 1})
                safe_retry = code in (429, 500, 502, 503, 504) or code is None
                if not safe_retry or attempt == self.args.retries:
                    raise
                retry_after = getattr(error, 'headers', {}).get('Retry-After', '')
                delay = max(2 ** attempt, int(retry_after) if retry_after.isdigit() else 0)
                if delay > 60:
                    raise RuntimeError('Retry-After exceeds 60 seconds; stop and retry later') from error
                time.sleep(delay)


def run(args):
    if args.rate_limit < 1 or args.max_pages < 1 or args.timeout <= 0 or args.retries < 0:
        raise ValueError('Invalid run limits; rate-limit must be at least 1 second')
    if args.dry_run:
        print(json.dumps({'targets': ENDPOINTS, 'fields': 'All public response fields plus provenance',
                          'max_pages': args.max_pages, 'rate_limit': args.rate_limit, 'persists_data': False}, ensure_ascii=False))
        return
    if not args.authorized:
        raise ValueError('Site-owner authorization required; use --authorized only after obtaining it')
    directory = args.output / datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ')
    (directory / 'raw').mkdir(parents=True)
    fetcher = Fetcher(args, directory)
    report = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(), 'target': ROOT + '/activities',
              'authorization': 'Owner confirmed site permission in this conversation on 2026-10-14',
              'scope': 'Public activity API datasets only; no external project websites or account data', 'datasets': {}}
    try:
        robots = fetcher.get('/robots.txt', 'robots.txt')
        policy = urllib.robotparser.RobotFileParser()
        policy.parse(robots.decode().splitlines())
        for path in ['/activities', *ENDPOINTS.values()]:
            if not policy.can_fetch(USER_AGENT, ROOT + path):
                raise RuntimeError('robots.txt disallows ' + path)
        fetcher.get('/activities', 'activities.html')
        fetcher.get('/terms', 'terms.html')
        combined = []
        for kind, endpoint in ENDPOINTS.items():
            primary_url = endpoint + '?limit=1000'
            primary = parse_records(fetcher.get(primary_url, kind + '_1000.json'))
            check = parse_records(fetcher.get(endpoint + '?limit=5000', kind + '_5000.json'))
            small = parse_records(fetcher.get(endpoint + '?limit=1', kind + '_1.json'))
            if not primary or len(primary) >= 1000 or sorted(map(digest, primary)) != sorted(map(digest, check)):
                raise RuntimeError(kind + ': coverage check failed')
            if len(small) != 1 or digest(small[0]) not in set(map(digest, primary)):
                raise RuntimeError(kind + ': limit control check failed')
            timestamp = next(entry['fetched_at'] for entry in fetcher.manifest if entry['url'] == ROOT + primary_url)
            records = normalize(primary, kind, ROOT + primary_url, timestamp)
            combined.extend(records)
            fields = sorted({key for item in primary for key in item})
            names = [item['name'].strip().casefold() for item in primary]
            report['datasets'][kind] = {'raw_count': len(primary), 'exported_count': len(records),
                'exact_duplicates': len(primary) - len(records), 'duplicate_names': len(names) - len(set(names)),
                'coverage': 'limit=1000 and limit=5000 identical; result below cap; limit=1 honored',
                'fields': fields, 'missing_fields': {key: sum(item.get(key) in (None, '', []) for item in primary) for key in fields}}
            (directory / (kind + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))
            (directory / (kind + '.csv')).write_text(csv_content(records), encoding='utf-8-sig')
        (directory / 'activities.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in combined))
        (directory / 'activities.csv').write_text(csv_content(combined), encoding='utf-8-sig')
        report.update(status='complete_public_api_snapshot', records_extracted=len(combined),
                      completeness_limit='Validated the exposed unfiltered API lists; no claim about hidden/backend records or third-party site accuracy')
    except Exception as error:
        report.update(status='failed', failure_type=type(error).__name__, failure=str(error))
        raise
    finally:
        report.update(finished_at=datetime.now(timezone.utc).isoformat(), pages_requested=fetcher.requests,
                      pages_succeeded=len(fetcher.manifest), pages_failed=len(fetcher.errors),
                      request_errors=fetcher.errors, responses=fetcher.manifest)
        (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'event': 'finished', 'status': report['status'], 'directory': str(directory)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--authorized', action='store_true')
    parser.add_argument('--max-pages', type=int, default=15)
    parser.add_argument('--rate-limit', type=float, default=1.5)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--retries', type=int, default=2)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'data')
    run(parser.parse_args())
