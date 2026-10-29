"""Inspect inline structured data without executing site JavaScript."""
import json
import re
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from collegex_crawler import Fetcher, ROOT, digest


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts, self.meta, self.links, self.semantic = [], [], [], []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            self.current = {'attrs': attrs, 'text': ''}
        elif tag == 'meta':
            self.meta.append(attrs)
        elif tag == 'link':
            self.links.append(attrs)
        if any(key in attrs for key in ('itemscope', 'itemprop', 'itemtype', 'typeof', 'vocab', 'property')) and tag != 'meta':
            self.semantic.append({'tag': tag, 'attributes': attrs})

    def handle_data(self, data):
        if self.current is not None:
            self.current['text'] += data

    def handle_endtag(self, tag):
        if tag == 'script' and self.current is not None:
            self.scripts.append(self.current)
            self.current = None


def parse_page(html):
    parser = PageParser()
    parser.feed(html)
    ld, flight, other_json = [], [], []
    for script in parser.scripts:
        attrs, body = script['attrs'], script['text']
        if attrs.get('type', '').lower() == 'application/ld+json':
            ld.append(json.loads(body))
        elif attrs.get('type', '').lower() == 'application/json' or attrs.get('id') == '__NEXT_DATA__':
            other_json.append(json.loads(body))
        elif body.startswith('self.__next_f.push('):
            payload = json.loads(body[len('self.__next_f.push('):].removesuffix(')'))
            flight.append(payload)
    return parser, ld, flight, other_json


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def decode_flight(flight):
    decoded, unparsed = [], []
    for payload in flight:
        if len(payload) < 2 or not isinstance(payload[1], str):
            continue
        for line in payload[1].splitlines():
            if ':' not in line:
                unparsed.append(line)
                continue
            key, value = line.split(':', 1)
            kind = 'import' if value.startswith('I[') else 'resource_hint' if value.startswith('HL[') else 'json'
            if kind == 'import':
                value = value[1:]
            elif kind == 'resource_hint':
                value = value[2:]
            try:
                decoded.append({'key': key, 'kind': kind, 'value': json.loads(value)})
            except json.JSONDecodeError:
                unparsed.append(line)
    return decoded, unparsed


def main():
    import argparse
    args = argparse.Namespace(retries=1, max_pages=20, rate_limit=1.5, timeout=30)
    root = Path(__file__).parent
    status = json.loads((root / '抓取核查状态_20261014.json').read_text())
    run = root / status['latest_run']
    audit = run / ('structured_audit_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    (audit / 'raw').mkdir(parents=True)
    fetcher = Fetcher(args, audit)
    html = fetcher.get('/activities', 'activities.html').decode()
    parser, ld, flight, other = parse_page(html)
    decoded, unparsed = decode_flight(flight)
    chunks = sorted({script['attrs']['src'] for script in parser.scripts if script['attrs'].get('src', '').startswith('/_next/static/chunks/')})
    chunk_results = []
    for path in chunks:
        body = fetcher.get(path, path.rsplit('/', 1)[1]).decode()
        endpoints = sorted(set(re.findall(r'/api/[a-zA-Z0-9_/?=&.\-]+', body)))
        chunk_results.append({'url': ROOT + path, 'bytes': len(body.encode()), 'api_paths': endpoints,
                              'is_activity_module': '/api/competitions' in body and '/api/summer-programs' in body})
    records = [json.loads(line) for line in (run / 'activities.jsonl').read_text().splitlines()]
    existing_names = {record['data']['name'].strip().casefold() for record in records}
    candidates = []
    for value in [*ld, *other, *[entry['value'] for entry in decoded]]:
        for node in walk(value):
            if isinstance(node, dict) and isinstance(node.get('name'), str):
                candidates.append({'name': node['name'], 'type': node.get('@type'), 'fields': sorted(node),
                                   'matches_existing_activity': node['name'].strip().casefold() in existing_names})
    page_meta = {'source_url': ROOT + '/activities', 'json_ld': ld, 'meta': parser.meta,
                 'canonical_links': [link for link in parser.links if link.get('rel') == 'canonical'],
                 'note': 'Page/site metadata applies to the page; not individual competition or summer-program records.'}
    (audit / 'page_metadata.json').write_text(json.dumps(page_meta, ensure_ascii=False, indent=2) + '\n')
    (audit / 'next_flight_decoded.json').write_text(json.dumps(decoded, ensure_ascii=False, indent=2) + '\n')
    (audit / 'next_flight_unparsed.json').write_text(json.dumps(unparsed, ensure_ascii=False, indent=2) + '\n')
    report = {'status': 'inspection_pending_review', 'checked_at': datetime.now(timezone.utc).isoformat(),
              'existing_record_count': len(records), 'json_ld_blocks': len(ld), 'other_json_blocks': len(other),
              'semantic_html_nodes': parser.semantic, 'json_ld_types': dict(Counter(node.get('@type', 'unknown') for obj in ld for node in walk(obj) if isinstance(node, dict) and '@type' in node)),
              'flight_payloads': len(flight), 'flight_decoded_rows': len(decoded), 'flight_unparsed_rows': len(unparsed),
              'named_structured_objects': candidates, 'chunks': chunk_results, 'responses': fetcher.manifest,
              'request_errors': fetcher.errors, 'record_content_hashes_before': [digest(record) for record in records]}
    (audit / 'audit_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'audit': str(audit), 'json_ld_blocks': len(ld), 'flight_unparsed_rows': len(unparsed), 'chunk_count': len(chunks), 'named_objects': candidates}, ensure_ascii=False))


if __name__ == '__main__':
    main()
