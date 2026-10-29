"""Apply reviewed field decisions, preserving upstream snapshots and stable IDs."""
import csv
import hashlib
import io
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

FIELDS = ('official_website', 'fees_2027', 'application_dates_2027', 'eligibility')


def export_csv(records):
    meta = ['record_id', 'activity_type', 'source_url', 'source_page_url', 'crawled_at', 'canonical_url']
    fields = sorted({key for record in records for key in record['data']})
    proof = [f'{field}_{suffix}' for field in FIELDS for suffix in ('status', 'source', 'verified_on', 'applicability', 'reason')]
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=meta + fields + proof)
    writer.writeheader()
    for record in records:
        row = {**{key: record[key] for key in meta}, **record['data']}
        for field in FIELDS:
            claim = record['official_verification']['fields'][field]
            for suffix, key in [('status', 'status'), ('source', 'source_url'), ('verified_on', 'verified_on'), ('applicability', 'applicability'), ('reason', 'reason')]:
                row[f'{field}_{suffix}'] = claim.get(key)
        writer.writerow(row)
    return output.getvalue()


def make_claim(value, page, directory, extra=None):
    if not page or page['status'] != 'page_fetched_unreviewed':
        raise ValueError('Cannot verify a field without a successfully retrieved source')
    claim = {'value': value, 'status': 'verified_from_official_page', 'source_url': page.get('final_url', page['requested_url']),
             'requested_source_url': page['requested_url'], 'checked_at': page['checked_at'],
             'verified_on': datetime.fromisoformat(page['checked_at']).astimezone(timezone(timedelta(hours=8))).date().isoformat(),
             'evidence_file': str(Path(directory) / page['folder'] / page['text_file']),
             'evidence_sha256': page['content_sha256'], 'reason': None}
    if extra:
        claim.update({key: val for key, val in extra.items() if key != 'value'})
    return claim


def main():
    root = Path(__file__).parent
    status_path = root / '抓取核查状态_20261014.json'
    status = json.loads(status_path.read_text())
    if 'latest_checked_on' in status.get('official_verification_2027', {}):
        raise ValueError('Later incremental verification exists; use continue_official_verification.py to preserve it')
    run = root / status['latest_run']
    directory = run / 'official_verification_2027'
    pages = json.loads((directory / 'source_index.json').read_text())
    by_url = {page['requested_url']: page for page in pages}
    decisions = json.loads((directory / 'reviewed_decisions.json').read_text())
    approved = json.loads((directory / 'approved_competition_websites.json').read_text())
    indexed_path = directory / 'indexed_website_approvals.json'
    indexed = json.loads(indexed_path.read_text()) if indexed_path.exists() else []
    inventory = json.loads((directory / 'inventory.json').read_text())
    comp_inventory = json.loads((directory / 'competition_inventory.json').read_text())
    backup = directory / 'before_enrichment'
    backup.mkdir(exist_ok=True)
    stems = ('activities', 'competitions', 'summer_programs')
    for stem in stems:
        for extension in ('csv', 'jsonl'):
            name = f'{stem}.{extension}'
            if not (backup / name).exists():
                shutil.copyfile(run / name, backup / name)
    records = [json.loads(line) for line in (backup / 'activities.jsonl').read_text().splitlines()]
    original_by_id = {record['record_id']: record for record in inventory['records']}
    original_by_id.update({record['record_id']: record for record in comp_inventory['records'] if record['url']})
    approved_by_id = {entry['record_id']: entry for entry in approved}
    indexed_by_id = {entry['record_id']: entry for entry in indexed}
    changes = []
    for record in records:
        original_url = original_by_id[record['record_id']]['url']
        page = by_url.get(original_url)
        invalid = bool(record['data']['name'][:1].isdigit() and not record['canonical_url'])
        reason = 'upstream_malformed_record' if invalid else ('official_identity_unresolved' if not original_url else (page['status'] if page else 'source_not_confirmed'))
        fields = {field: {'value': None, 'status': 'not_confirmed', 'source_url': None, 'verified_on': None,
                          'reason': reason if reason != 'page_fetched_unreviewed' else 'not_confirmed_for_target_year_or_scope'} for field in FIELDS}
        notes = []
        if record['record_id'] in approved_by_id:
            website = approved_by_id[record['record_id']]
            fields['official_website'] = make_claim(website['official_url'], by_url[website['source_url']], directory,
                                                   {'applicability': 'official_project_or_organizer_information_page'})
        elif record['record_id'] in indexed_by_id:
            entry = indexed_by_id[record['record_id']]
            evidence = directory / entry['evidence_file']
            if not evidence.exists() or entry['source_url'] not in evidence.read_text():
                raise ValueError('Missing indexed official URL evidence')
            fields['official_website'] = {'value': entry['official_url'], 'status': 'official_identity_verified_from_public_search_index',
                'source_url': entry['source_url'], 'verified_on': '2026-10-14',
                'evidence_file': str(evidence), 'evidence_sha256': hashlib.sha256(evidence.read_bytes()).hexdigest(),
                'applicability': 'official_identity_only_live_page_not_verified', 'reason': None}
            notes.append('官网身份由公开检索索引中的主办方官方页面确认；直接访问受限或未验证，不代表2027届资料已公布。')
        for decision in decisions:
            if (decision.get('applies_to_url', decision['url']) == original_url or decision.get('record_id') == record['record_id']):
                source = by_url[decision['url']]
                text = (directory / source['folder'] / source['text_file']).read_text()
                assert hashlib.sha256(text.encode()).hexdigest() == source['content_sha256']
                lines = text.splitlines()
                for field, extra in decision['fields'].items():
                    start, end = extra['lines']
                    if start < 1 or end < start or end > len(lines):
                        raise ValueError('Invalid source line reference: ' + decision['url'])
                    fields[field] = make_claim(extra['value'], source, directory, extra)
                if fields['official_website']['value'] is None:
                    website_source = page if page and page['status'] == 'page_fetched_unreviewed' else source
                    fields['official_website'] = make_claim(website_source.get('final_url', website_source['requested_url']), website_source, directory,
                                                          {'applicability': 'official_project_information_page'})
                notes.extend(decision.get('notes', []))
        for field in FIELDS:
            key = 'official_eligibility' if field == 'eligibility' else field
            record['data'][key] = fields[field]['value']
        if fields['official_website']['value']:
            key = 'website' if record['activity_type'] == 'competitions' else 'url'
            if not record['data'].get(key):
                record['data'][key] = fields['official_website']['value']
                record['canonical_url'] = fields['official_website']['value']
                changes.append({'record_id': record['record_id'], 'field': key, 'new_value': record['data'][key]})
        record['official_verification'] = {'target_year': 2027, 'checked_on': '2026-10-14',
            'source_access_status': page['status'] if page else reason,
            'record_quality': 'suspected_upstream_row_fragment' if invalid else 'retained',
            'notes': list(dict.fromkeys(notes)), 'fields': fields}
    if len(records) != 485 or len({r['record_id'] for r in records}) != 485:
        raise ValueError('Record identity/count changed unexpectedly')
    counts = {field: sum(record['official_verification']['fields'][field]['value'] is not None for record in records) for field in FIELDS}
    report = {'status': 'completed_bounded_verification_pass', 'checked_on': '2026-10-14', 'target_year': 2027,
              'records': 485, 'verified_field_counts': counts,
              'null_field_counts': {field: 485-count for field, count in counts.items()},
              'records_with_any_verified_field': sum(any(claim['value'] is not None for claim in record['official_verification']['fields'].values()) for record in records),
              'new_upstream_website_links': len(changes),
              'source_page_status_counts': dict(Counter(page['status'] for page in pages)),
              'source_pages_attempted': len(pages), 'reviewed_decision_sources': len(decisions),
              'malformed_records_retained': [record['record_id'] for record in records if record['official_verification']['record_quality'] != 'retained'],
              'policy': '2027 fees/application dates only when confirmed. General eligibility is explicitly labeled as current guidance, not confirmed 2027 rules. Upstream cost_range and key_dates remain historical unverified source values.',
              'limitations': 'A bounded pass over available official pages and up to two relevant linked pages per reachable program. Null means unconfirmed; it does not assert that the information does not exist elsewhere. Access blocks were not bypassed.',
              'before_enrichment': str(backup), 'website_changes': changes}
    outputs = {}
    for stem in stems:
        subset = records if stem == 'activities' else [r for r in records if r['activity_type'] == stem]
        outputs[run / (stem + '.jsonl')] = (''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in subset), 'utf-8')
        outputs[run / (stem + '.csv')] = (export_csv(subset), 'utf-8-sig')
    for path, (content, encoding) in outputs.items():
        temporary = path.with_suffix(path.suffix + '.new')
        temporary.write_text(content, encoding=encoding)
    for path in outputs:
        os.replace(path.with_suffix(path.suffix + '.new'), path)
    (directory / 'enrichment_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    status['official_verification_2027'] = {'status': report['status'], 'report': str((directory / 'enrichment_report.json').relative_to(root)), 'counts': counts, 'new_website_links': len(changes)}
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'records', 'verified_field_counts', 'new_upstream_website_links', 'source_pages_attempted', 'records_with_any_verified_field')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
