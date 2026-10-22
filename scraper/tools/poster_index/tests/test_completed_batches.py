import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from poster_index import jisi


class CompletedBatchTests(unittest.TestCase):
    def fixture(self, root, name='run', **updates):
        run = root / 'output/incremental' / name
        site = run / 'sou_tools'
        (site / 'processed').mkdir(parents=True)
        (site / 'processed/records.jsonl').write_text('{"id":"new"}\n')
        entry = {'site': 'sou_tools', 'selected_topics': 1,
                 'list': {'pages_failed': 0, 'seed_summaries': [{'pages':[1], 'expected_allPage':1}]},
                 'details': {'detail_missing_ids': 0, 'details_failed':0},
                 'assets': {'missing_asset_downloads':0}}
        entry.update(updates)
        (run / 'incremental_summary.json').write_text(json.dumps({'finished_at':'2026-10-13', 'sites':[entry]}))
        return site / 'processed/records.jsonl'

    def test_completed_batch_admitted(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(jisi,'RECORD_BATCHES',[]):
            root=Path(tmp); wanted=self.fixture(root)
            paths, excluded=jisi.discover_record_batches(root)
            self.assertEqual(paths,[wanted]);self.assertEqual(excluded,[])

    def test_failed_and_truncated_batches_excluded(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(jisi,'RECORD_BATCHES',[]):
            root=Path(tmp)
            self.fixture(root,'failed',list={'pages_failed':1})
            self.fixture(root,'truncated',list={'pages_failed':0,'seed_summaries':[{'pages':[1],'expected_allPage':2}]})
            self.fixture(root,'detail',details={'detail_missing_ids':1})
            paths, excluded=jisi.discover_record_batches(root)
            self.assertEqual(paths,[]);self.assertEqual(len(excluded),3)

    def test_absent_summary_not_inferred_from_records(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(jisi,'RECORD_BATCHES',[]):
            root=Path(tmp); self.fixture(root)
            (root/'output/incremental/run/incremental_summary.json').unlink()
            paths,excluded=jisi.discover_record_batches(root)
            self.assertEqual(paths,[]);self.assertEqual(len(excluded),1)

    def test_only_evidenced_404_exemptions_admitted(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(jisi,'RECORD_BATCHES',[]):
            root=Path(tmp)
            wanted=self.fixture(root,assets={'missing_asset_downloads':1,'failed_urls_by_category':{'http_404_not_found':['https://example.test/missing.pdf']}})
            paths,_=jisi.discover_record_batches(root);self.assertEqual(paths,[])
            reports=wanted.parent.parent/'reports';reports.mkdir()
            (reports/'asset_exemptions.json').write_text(json.dumps([{'url':'https://example.test/missing.pdf','category':'http_404_not_found'}]))
            paths,excluded=jisi.discover_record_batches(root)
            self.assertEqual(paths,[wanted]);self.assertEqual(excluded,[])

    def test_record_count_must_match_completion_summary(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(jisi,'RECORD_BATCHES',[]):
            root=Path(tmp);self.fixture(root,selected_topics=2)
            paths,_=jisi.discover_record_batches(root);self.assertEqual(paths,[])
