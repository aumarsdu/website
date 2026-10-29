"""Merge reviewed evidence into current exports without replaying old enrichment.

Usage: python3 -B continue_official_verification.py --pass-dir PATH
Only empty fields are filled. Existing claims and original nonempty values are retained.
"""
import argparse
import copy
import csv
import hashlib
import io
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from apply_official_verification import FIELDS, export_csv, make_claim


def merge(records, decisions, pages, directory):
    result = copy.deepcopy(records)
    by_id = {r['record_id']: r for r in result}
    changes = []
    for decision in decisions:
        record = by_id[decision['record_id']]
        if record['official_verification']['record_quality'] != 'retained':
            raise ValueError('Cannot enrich malformed records')
        page = pages[decision['url']]
        evidence = directory / page['folder'] / page['text_file']
        text = evidence.read_text()
        if hashlib.sha256(text.encode()).hexdigest() != page['content_sha256']:
            raise ValueError('Evidence hash mismatch')
        for field, extra in decision['fields'].items():
            if field not in FIELDS:
                raise ValueError('Unknown field')
            for start, end in [extra['lines']] + extra.get('additional_evidence_lines', []):
                if not 1 <= start <= end <= len(text.splitlines()):
                    raise ValueError('Invalid evidence lines')
            old = record['official_verification']['fields'][field]
            if old['value'] is not None:
                continue
            claim = make_claim(extra['value'], page, directory, extra)
            record['official_verification']['fields'][field] = claim
            key = 'official_eligibility' if field == 'eligibility' else field
            record['data'][key] = claim['value']
            record['official_verification']['checked_on'] = claim['verified_on']
            record['official_verification']['source_access_status'] = page['status']
            record['official_verification']['notes'] = list(dict.fromkeys(
                record['official_verification']['notes'] + decision.get('notes', [])))
            if field == 'official_website':
                key = 'website' if record['activity_type'] == 'competitions' else 'url'
                if not record['data'].get(key):
                    record['data'][key] = claim['value']
                    record['canonical_url'] = claim['value']
            changes.append({'record_id': record['record_id'], 'field': field,
                            'value': claim['value'], 'source_url': claim['source_url'],
                            'verified_on': claim['verified_on']})
    return result, changes


def focused_csv(records):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['记录ID', '类型', '名称', '上游链接_未作默认核验', '官网访问状态', '记录质量', '备注'] +
                    [c for f in FIELDS for c in [f, f+'_来源', f+'_核验日期', f+'_适用范围', f+'_状态或留空原因']])
    for r in records:
        v = r['official_verification']
        row = [r['record_id'], r['activity_type'], r['data']['name'],
               r['data'].get('website') or r['data'].get('url'), v['source_access_status'],
               v['record_quality'], '；'.join(v['notes'])]
        for f in FIELDS:
            c = v['fields'][f]
            row.extend([c['value'], c['source_url'], c['verified_on'], c.get('applicability'),
                        c.get('reason') or c['status']])
        writer.writerow(row)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pass-dir', type=Path, required=True)
    args = parser.parse_args()
    directory = args.pass_dir.resolve()
    if (directory / 'enrichment_report.json').exists():
        raise ValueError('Pass already applied; use its report instead of replaying')
    run = directory.parent.parent
    root = Path(__file__).resolve().parent
    records = [json.loads(s) for s in (run / 'activities.jsonl').read_text().splitlines()]
    pages = json.loads((directory / 'source_index.json').read_text())
    decisions = json.loads((directory / 'reviewed_decisions.json').read_text())
    updated, changes = merge(records, decisions, {p['requested_url']: p for p in pages}, directory)
    assert len(updated) == 485
    assert [r['record_id'] for r in records] == [r['record_id'] for r in updated]
    backup = directory / 'before_enrichment'
    backup.mkdir(exist_ok=False)
    outputs = {}
    for stem in ('activities', 'competitions', 'summer_programs'):
        subset = updated if stem == 'activities' else [r for r in updated if r['activity_type'] == stem]
        for ext in ('jsonl', 'csv'):
            path = run / (stem+'.'+ext)
            shutil.copyfile(path, backup / path.name)
            outputs[path] = ((''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in subset), 'utf-8')
                             if ext == 'jsonl' else (export_csv(subset), 'utf-8-sig'))
    focused = directory.parent / '2027官网核验表.csv'
    shutil.copyfile(focused, backup / focused.name)
    outputs[focused] = (focused_csv(updated), 'utf-8-sig')
    for path, (content, encoding) in outputs.items():
        path.with_suffix(path.suffix+'.new').write_text(content, encoding=encoding)
    for path in outputs:
        os.replace(path.with_suffix(path.suffix+'.new'), path)
    counts = {f: sum(r['official_verification']['fields'][f]['value'] is not None for r in updated) for f in FIELDS}
    report = {'status': 'completed_bounded_verification_pass', 'target_year': 2027,
              'checked_on': max(c['verified_on'] for c in changes), 'records': len(updated),
              'verified_field_counts': counts, 'null_field_counts': {f:485-n for f,n in counts.items()},
              'added_field_counts': dict(Counter(c['field'] for c in changes)),
              'changed_records': len({c['record_id'] for c in changes}),
              'source_pages_attempted': len(pages), 'source_page_status_counts': dict(Counter(p['status'] for p in pages)),
              'changes': changes, 'before_enrichment': str(backup),
              'limitations': 'Bounded public-site pass. Old claims retain original verification dates. General eligibility is labeled; unknown year, scope or identity remains null.'}
    (directory / 'enrichment_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    status_path = root / '抓取核查状态_20261014.json'
    shutil.copyfile(status_path, backup / status_path.name)
    status = json.loads(status_path.read_text())
    status['official_verification_2027'].update(report=str((directory/'enrichment_report.json').relative_to(root)), counts=counts,
        latest_checked_on=report['checked_on'], added_field_counts=report['added_field_counts'])
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('changes',)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
