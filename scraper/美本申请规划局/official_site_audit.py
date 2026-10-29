"""Bounded, robots-aware read-only discovery of public program pages.

Output is evidence for review, never automatically verified fee/deadline claims.
"""
import argparse
import concurrent.futures
import hashlib
import ipaddress
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

UA = 'CollegeXOfficialDataVerification/1.0 (public program information research)'
LOCK = threading.Lock()
HOSTS = {}
COUNT = 0
CAP = 1600
DELAY = 1.5
TIMEOUT = 15
RETRIES = 0
KEYS = re.compile(r'cost|tuition|fees?|pricing|deadline|apply|application|admission|eligib|requirement|2027|费用|报名|申请|资格', re.I)


def valid_url(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('non_public_url')
    host = parts.hostname.lower()
    if host == 'localhost' or host.endswith(('.local', '.internal')):
        raise ValueError('non_public_host')
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError('non_public_ip')
    except ValueError as error:
        if str(error) == 'non_public_ip':
            raise
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path or '/', parts.query, ''))


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        valid_url(newurl)
        if re.search(r'/(login|signin|sign-in|auth)(/|\?|$)', newurl, re.I):
            raise ValueError('authentication_redirect')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def download_once(url):
    global COUNT
    valid_url(url)
    host = urllib.parse.urlsplit(url).netloc.lower()
    with LOCK:
        state = HOSTS.setdefault(host, {'lock': threading.Lock(), 'last': 0})
    with state['lock']:
        delay = max(DELAY, state.get('crawl_delay', 0))
        if delay > 60:
            raise RuntimeError('robots_crawl_delay_exceeds_run_limit')
        time.sleep(max(0, delay - (time.monotonic() - state['last'])))
        with LOCK:
            if COUNT >= CAP:
                raise RuntimeError('request_cap')
            COUNT += 1
        state['last'] = time.monotonic()
        request = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,text/plain;q=0.9'})
        with urllib.request.build_opener(PublicRedirect()).open(request, timeout=TIMEOUT) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('response_too_large')
            content_type = response.headers.get('Content-Type', '')
            if not any(kind in content_type for kind in ('text/', 'html', 'json')):
                raise ValueError('unsupported_content_type:' + content_type.split(';')[0])
            return raw.decode(response.headers.get_content_charset() or 'utf-8', errors='replace'), response.url


def download(url):
    for attempt in range(RETRIES + 1):
        try:
            return download_once(url)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            code = getattr(error, 'code', None)
            if attempt == RETRIES or (code is not None and code not in (429, 500, 502, 503, 504)):
                raise
            retry_after = getattr(error, 'headers', {}).get('Retry-After', '')
            if retry_after and not retry_after.isdigit():
                raise
            wait = max(2 ** attempt, int(retry_after) if retry_after else 0)
            if wait > 60:
                raise RuntimeError('retry_after_exceeds_run_limit') from error
            time.sleep(wait)


ROBOTS = {}
ROBOTS_LOCK = threading.Lock()


def robots_allowed(url):
    origin = '{0.scheme}://{0.netloc}'.format(urllib.parse.urlsplit(url))
    with ROBOTS_LOCK:
        future = ROBOTS.get(origin)
        if future is None:
            future = concurrent.futures.Future()
            ROBOTS[origin] = future
            owner = True
        else:
            owner = False
    if owner:
        try:
            text, final = download(origin + '/robots.txt')
            if '<html' in text[:500].lower():
                future.set_result(('robots_invalid_html', None))
            else:
                policy = urllib.robotparser.RobotFileParser()
                policy.parse(text.splitlines())
                crawl_delay = policy.crawl_delay(UA) or policy.crawl_delay('*') or 0
                request_rate = policy.request_rate(UA) or policy.request_rate('*')
                if request_rate and request_rate.requests:
                    crawl_delay = max(crawl_delay, request_rate.seconds / request_rate.requests)
                with LOCK:
                    HOSTS[urllib.parse.urlsplit(url).netloc.lower()]['crawl_delay'] = crawl_delay
                future.set_result(('checked', policy))
        except urllib.error.HTTPError as error:
            future.set_result(('robots_404_allow', None) if error.code in (404, 410) else ('robots_http_' + str(error.code), None))
        except Exception as error:
            future.set_result(('robots_unavailable_' + type(error).__name__, None))
    state, policy = future.result()
    if state == 'robots_404_allow':
        return True, state
    if state != 'checked':
        return False, state
    return policy.can_fetch(UA, url), state


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.lines, self.links = [], []
        self.anchor, self.href = [], None
        self.in_title, self.title = False, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style', 'noscript', 'svg'):
            self.skip += 1
        if tag == 'title':
            self.in_title = True
        if tag == 'a':
            self.href, self.anchor = attrs.get('href'), []

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'svg'):
            self.skip = max(0, self.skip - 1)
        if tag == 'title':
            self.in_title = False
        if tag == 'a' and self.href:
            self.links.append({'href': self.href, 'label': ' '.join(self.anchor)})
            self.href = None

    def handle_data(self, data):
        if self.skip:
            return
        text = re.sub(r'\s+', ' ', data).strip()
        if text:
            self.lines.append(text)
            if self.in_title:
                self.title.append(text)
            if self.href:
                self.anchor.append(text)


def inspect(url, directory):
    result = {'requested_url': url, 'checked_at': datetime.now(timezone.utc).isoformat()}
    try:
        permitted, policy = robots_allowed(url)
        result['robots'] = policy
        if not permitted:
            result['status'] = 'robots_blocked_or_unknown'
            return result
        html, final = download(url)
        result['final_url'] = final
        if re.search(r'captcha|verify you are human|access denied|just a moment', html[:15000], re.I):
            result['status'] = 'access_challenge'
            return result
        parser = Page()
        parser.feed(html)
        text = '\n'.join(parser.lines)
        key = hashlib.sha256(url.encode()).hexdigest()[:20]
        (directory / (key + '.txt')).write_text(text)
        snippets = []
        for index, line in enumerate(parser.lines):
            if KEYS.search(line):
                snippets.append({'line': index + 1, 'text': ' '.join(parser.lines[max(0, index-1):index+4])[:1600]})
        origin = urllib.parse.urlsplit(final)
        links = []
        for link in parser.links:
            href = urllib.parse.urljoin(final, link['href'])
            if urllib.parse.urlsplit(href).netloc == origin.netloc and KEYS.search(link['label'] + ' ' + href):
                if not re.search(r'login|signin|donate|privacy|contact|mailto:|\.pdf(?:$|\?)', href, re.I):
                    links.append({'url': href.split('#')[0], 'label': link['label']})
        result.update(status='page_fetched_unreviewed', title=' '.join(parser.title), text_file=key + '.txt',
                      content_sha256=hashlib.sha256(text.encode()).hexdigest(), text_length=len(text),
                      years=sorted(set(re.findall(r'\b20[2-3][0-9]\b', text))),
                      snippets=snippets[:100], related_links=list({x['url']: x for x in links}.values())[:40])
    except urllib.error.HTTPError as error:
        result.update(status='http_' + str(error.code))
    except Exception as error:
        result.update(status='fetch_failed', error_type=type(error).__name__, reason=str(error)[:160])
    return result


def main():
    global CAP, DELAY, TIMEOUT, RETRIES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4, choices=range(1, 5))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--max-pages', type=int, default=1600)
    parser.add_argument('--rate-limit', type=float, default=1.5)
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--retries', type=int, default=0, choices=range(3))
    args = parser.parse_args()
    if args.max_pages < 1 or args.rate_limit < 1 or args.timeout <= 0:
        parser.error('Invalid limits: max-pages>=1, rate-limit>=1, timeout>0 required')
    CAP, DELAY, TIMEOUT, RETRIES = args.max_pages, args.rate_limit, args.timeout, args.retries
    inventory = json.loads(args.inventory.read_text())
    if args.dry_run:
        print(json.dumps({'dry_run': True, 'unique_urls': len({x['url'] for x in inventory['records'] if x['url']}),
                          'max_pages': CAP, 'rate_limit': DELAY, 'timeout': TIMEOUT, 'retries': RETRIES,
                          'output_written': False, 'requests': 0}))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    source_dir = args.output / 'sources'
    source_dir.mkdir(exist_ok=True)
    urls = sorted({x['url'] for x in inventory['records'] if x['url']})
    result_file = args.output / 'pages.jsonl'
    done = set()
    if result_file.exists():
        done = {json.loads(line)['requested_url'] for line in result_file.read_text().splitlines()}
    targets = [url for url in urls if url not in done]
    with result_file.open('a') as stream, concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(inspect, url, source_dir): url for url in targets}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            result = future.result()
            stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            stream.flush()
            if index % 20 == 0 or index == len(targets):
                print(json.dumps({'completed': index, 'target_count': len(targets), 'requests': COUNT}), flush=True)
    print(json.dumps({'status': 'discovery_complete_requires_review', 'urls': len(urls), 'requests_this_run': COUNT}), flush=True)


if __name__ == '__main__':
    main()
