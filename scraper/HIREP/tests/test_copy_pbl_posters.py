import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.copy_pbl_posters import copy_posters


class CopyPblPostersTest(unittest.TestCase):
    def test_copy_posters_preserves_asset_tree_and_avoids_overwrite(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output_pbl_incremental"
            assets = output / "assets"
            poster = assets / "理科" / "化学" / "课题 A" / "海报.jpg"
            thumbnail = assets / "理科" / "化学" / "课题 A" / "缩略图.jpg"
            poster.parent.mkdir(parents=True)
            poster.write_bytes(b"poster")
            thumbnail.write_bytes(b"thumbnail")
            manifest = [
                {"field": "attachmentId", "file": str(poster)},
                {"field": "thumbnailId", "file": str(thumbnail)},
            ]
            manifest_path = output / "processed" / "asset_manifest.jsonl"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text("".join(json.dumps(item) + "\n" for item in manifest), encoding="utf-8")
            destination = root / "posters"

            first = copy_posters(output, destination, dry_run=False)
            second = copy_posters(output, destination, dry_run=False)

            target = destination / "理科" / "化学" / "课题 A" / "海报.jpg"
            self.assertTrue(target.is_file())
            self.assertEqual(target.read_bytes(), b"poster")
            self.assertEqual(first["copied"], 1)
            self.assertEqual(second["copied"], 0)
            self.assertEqual(second["skipped_existing"], 1)

    def test_copy_posters_dry_run_does_not_create_destination(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output_pbl_incremental"
            poster = output / "assets" / "理科" / "化学" / "课题 A" / "海报.jpg"
            poster.parent.mkdir(parents=True)
            poster.write_bytes(b"poster")
            manifest_path = output / "processed" / "asset_manifest.jsonl"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(json.dumps({"field": "attachmentId", "file": str(poster)}) + "\n", encoding="utf-8")
            destination = root / "posters"

            stats = copy_posters(output, destination, dry_run=True)

            self.assertEqual(stats["planned"], 1)
            self.assertEqual(stats["copied"], 0)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
