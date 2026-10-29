import csv
import io
import json
import unittest
from pathlib import Path

from collegex_crawler import canonical_url, csv_content, digest, normalize, parse_records


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.records = parse_records((Path(__file__).parent / 'tests/fixtures/activities.json').read_bytes())

    def test_saved_api_parser(self):
        self.assertEqual(len(self.records), 2)
        self.assertTrue(all(item['name'] for item in self.records))

    def test_schema_rejects_bad_input(self):
        for raw in ['{}', '[{}]', '[{"name":""}]', '[null]']:
            with self.assertRaises(ValueError):
                parse_records(raw)

    def test_url_normalization(self):
        self.assertEqual(canonical_url('https://EXAMPLE.com/a#section'), 'https://example.com/a')
        self.assertIsNone(canonical_url(''))
        with self.assertRaises(ValueError):
            canonical_url('javascript:void(0)')

    def test_dedup_preserves_distinct_programs(self):
        records = normalize(self.records + [self.records[0]], 'competitions', 'https://college-x.com/api/competitions', '2026-10-14')
        self.assertEqual(len(records), 2)
        self.assertNotEqual(records[0]['record_id'], records[1]['record_id'])
        self.assertEqual(digest(self.records[0]), digest(dict(reversed(list(self.records[0].items())))))

    def test_storage_roundtrip(self):
        records = normalize(self.records, 'competitions', 'https://college-x.com/api/competitions', '2026-10-14')
        self.assertEqual(json.loads(json.dumps(records[0], ensure_ascii=False)), records[0])
        rows = list(csv.DictReader(io.StringIO(csv_content(records))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['original_description'], self.records[0]['original_description'])


if __name__ == '__main__':
    unittest.main()
