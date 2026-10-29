import csv
import hashlib
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


class OfficialExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parent
        status = json.loads((cls.root / '抓取核查状态_20261014.json').read_text())
        cls.archive_path = cls.root / status['latest_run']
        cls.directory = cls.archive_path / 'official_verification_2027'
        cls.records = [json.loads(line) for line in (cls.archive_path / 'activities.jsonl').read_text().splitlines()]
        cls.before = [json.loads(line) for line in (cls.directory / 'before_enrichment/activities.jsonl').read_text().splitlines()]

    def test_record_identity_and_preservation(self):
        self.assertEqual(len(self.records), 485)
        self.assertEqual([r['record_id'] for r in self.records], [r['record_id'] for r in self.before])
        for current, original in zip(self.records, self.before):
            for key, value in original['data'].items():
                if key in ('website', 'url') and value in (None, ''):
                    continue
                self.assertEqual(current['data'][key], value)

    def test_claim_provenance_and_empty_values(self):
        for record in self.records:
            fields = record['official_verification']['fields']
            for field, claim in fields.items():
                data_key = 'official_eligibility' if field == 'eligibility' else field
                self.assertEqual(record['data'][data_key], claim['value'])
                if claim['value'] is None:
                    self.assertIsNone(claim['source_url'])
                    self.assertIsNone(claim['verified_on'])
                else:
                    date.fromisoformat(claim['verified_on'])
                    if claim.get('checked_at'):
                        self.assertEqual(claim['verified_on'], datetime.fromisoformat(claim['checked_at']).astimezone(timezone(timedelta(hours=8))).date().isoformat())
                    else:
                        self.assertEqual(claim['verified_on'], '2026-10-14')
                    evidence = Path(claim['evidence_file'])
                    self.assertTrue(evidence.is_file())
                    self.assertEqual(hashlib.sha256(evidence.read_bytes()).hexdigest(), claim['evidence_sha256'])
                    self.assertTrue(claim['source_url'].startswith(('https://', 'http://')))

    def test_csv_jsonl_roundtrip(self):
        for stem in ('activities', 'competitions', 'summer_programs'):
            subset = [json.loads(line) for line in (self.archive_path / (stem + '.jsonl')).read_text().splitlines()]
            with (self.archive_path / (stem + '.csv')).open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(subset))
            for row, record in zip(rows, subset):
                for key, value in record['data'].items():
                    self.assertEqual(row[key], '' if value is None else str(value))

    def test_2027_unknown_and_conflict_guards(self):
        by_name = {record['data']['name']: record for record in self.records}
        self.assertIsNone(by_name['Buffalo Pharmacy Summer Institute']['data']['application_dates_2027'])
        self.assertIsNone(by_name['Stanford University Mathematics Camp (SUMaC)']['data']['fees_2027'])
        self.assertIsNone(by_name['MIT: Women’s Technology Program']['data']['fees_2027'])
        for record in self.records:
            if record['official_verification']['record_quality'] == 'suspected_upstream_row_fragment':
                self.assertTrue(all(claim['value'] is None for claim in record['official_verification']['fields'].values()))

    def test_incremental_changes_preserve_previous_claims(self):
        directory = self.directory / 'pass_20261021'
        report = json.loads((directory / 'enrichment_report.json').read_text())
        baseline = [json.loads(line) for line in (directory / 'before_enrichment/activities.jsonl').read_text().splitlines()]
        permitted = {(c['record_id'], c['field']) for c in report['changes']}
        actual = set()
        for old, new in zip(baseline, self.records):
            self.assertEqual(old['record_id'], new['record_id'])
            for field in old['official_verification']['fields']:
                before = old['official_verification']['fields'][field]
                after = new['official_verification']['fields'][field]
                if before != after:
                    self.assertIsNone(before['value'])
                    self.assertIsNotNone(after['value'])
                    self.assertEqual(after['verified_on'], report['checked_on'])
                    actual.add((new['record_id'], field))
        self.assertEqual(actual, permitted)


if __name__ == '__main__':
    unittest.main()
