"""T05 asset registry cases: synthetic negatives plus real yanqu originals."""

import tempfile
import unittest
from pathlib import Path

from asset_registry import (
    AssetError,
    counts,
    derivation_chain,
    link_blob,
    register_location,
    safe_asset_path,
    sha256_stream,
)

SIDE = Path(__file__).resolve().parent


def make_image(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


class AssetRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "root"
        (self.root / "originals").mkdir(parents=True)
        make_image(self.root / "originals" / "a.png", b"png-bytes-a")
        make_image(self.root / "originals" / "b.png", b"png-bytes-b")
        self.blobs: dict = {}
        self.locations: dict = {}
        self.links: list = []

    def test_register_and_blob_dedup_on_rename(self) -> None:
        first = register_location(
            self.root, "originals/a.png", "original", self.blobs, self.locations
        )
        (self.root / "renamed").mkdir(exist_ok=True)
        (self.root / "renamed" / "a-renamed.png").write_bytes(b"png-bytes-a")
        second = register_location(
            self.root, "renamed/a-renamed.png", "original", self.blobs, self.locations
        )
        self.assertEqual(first["blob_sha256"], second["blob_sha256"])
        report = counts(self.blobs, self.locations, self.links)
        self.assertEqual(report["unique_blobs"], 1, "rename must not add a blob")
        self.assertEqual(report["file_locations"], 2)

    def test_same_content_multi_path_multi_project(self) -> None:
        register_location(
            self.root, "originals/a.png", "original", self.blobs, self.locations
        )
        digest = "x"
        (self.root / "copy.png").write_bytes(b"png-bytes-a")
        copy = register_location(
            self.root, "copy.png", "delivery", self.blobs, self.locations
        )
        digest = copy["blob_sha256"]
        link_blob(
            digest,
            "poster",
            self.blobs,
            self.locations,
            self.links,
            provider_project="P1",
        )
        link_blob(
            digest,
            "poster",
            self.blobs,
            self.locations,
            self.links,
            provider_project="P2",
        )
        self.assertEqual(len(self.links), 2)
        self.assertEqual(counts(self.blobs, self.locations, self.links)["links"], 2)

    def test_missing_file_visible(self) -> None:
        entry = register_location(
            self.root, "originals/gone.png", "original", self.blobs, self.locations
        )
        self.assertEqual(entry["status"], "missing")
        self.assertEqual(
            counts(self.blobs, self.locations, self.links)["missing_locations"], 1
        )

    def test_traversal_and_symlink_rejected(self) -> None:
        with self.assertRaisesRegex(AssetError, "path_out_of_scope"):
            safe_asset_path(self.root, "../outside.png")
        outside = Path(self.temp.name) / "outside.png"
        make_image(outside, b"x")
        (self.root / "escape.png").symlink_to(outside)
        with self.assertRaisesRegex(AssetError, "path_out_of_scope"):
            register_location(
                self.root, "escape.png", "original", self.blobs, self.locations
            )

    def test_derivation_chain_and_rename_trace(self) -> None:
        register_location(
            self.root, "originals/a.png", "original", self.blobs, self.locations
        )
        (self.root / "processed").mkdir()
        (self.root / "processed" / "a-ocr.png").write_bytes(b"png-bytes-a")
        register_location(
            self.root,
            "processed/a-ocr.png",
            "processed",
            self.blobs,
            self.locations,
            derived_from="originals/a.png",
        )
        chain = derivation_chain("processed/a-ocr.png", self.locations)
        self.assertEqual(chain, ["processed/a-ocr.png", "originals/a.png"])

    def test_derivation_cycle_detected(self) -> None:
        register_location(
            self.root,
            "originals/a.png",
            "original",
            self.blobs,
            self.locations,
            derived_from="originals/b.png",
        )
        register_location(
            self.root,
            "originals/b.png",
            "original",
            self.blobs,
            self.locations,
            derived_from="originals/a.png",
        )
        chain = derivation_chain("originals/a.png", self.locations)
        self.assertTrue(chain[-1].startswith("<cycle:"))

    def test_derivation_unknown_and_missing_visible(self) -> None:
        self.assertEqual(
            derivation_chain("nope.png", self.locations),
            ["nope.png", "<unknown_location>"],
        )
        register_location(
            self.root, "originals/gone.png", "original", self.blobs, self.locations
        )
        self.assertEqual(
            derivation_chain("originals/gone.png", self.locations),
            ["originals/gone.png", "<missing_file>"],
        )

    def test_link_requires_target(self) -> None:
        register_location(
            self.root, "originals/a.png", "original", self.blobs, self.locations
        )
        digest = self.locations["originals/a.png"]["blob_sha256"]
        with self.assertRaisesRegex(AssetError, "link_target_missing"):
            link_blob(digest, "poster", self.blobs, self.locations, self.links)
        with self.assertRaisesRegex(AssetError, "blob_unknown"):
            link_blob(
                "f" * 64,
                "poster",
                self.blobs,
                self.locations,
                self.links,
                source_record="SR-1",
            )

    def test_derived_from_must_be_known_location(self) -> None:
        register_location(
            self.root, "originals/a.png", "original", self.blobs, self.locations
        )
        digest = self.locations["originals/a.png"]["blob_sha256"]
        with self.assertRaisesRegex(AssetError, "derived_from_unknown"):
            link_blob(
                digest,
                "processed",
                self.blobs,
                self.locations,
                self.links,
                source_record="SR-1",
                derived_from_location="originals/gone.png",
            )

    def test_streaming_hash_matches_known(self) -> None:
        payload = b"png-bytes-a"
        import hashlib

        self.assertEqual(
            sha256_stream(self.root / "originals" / "a.png"),
            hashlib.sha256(payload).hexdigest(),
        )

    def test_real_yanqu_originals_register(self) -> None:
        root = SIDE.parent.parent.parent
        yanqu = root / "盐趣" / "盐趣7-9月项目合集"
        if not yanqu.is_dir():
            self.skipTest("yanqu collection not present")
        import json

        manifest = json.loads(
            (SIDE / "pilot_manifest.json").read_text(encoding="utf-8")
        )
        candidates = manifest["yanqu_original_image_candidates"]
        blobs: dict = {}
        locations: dict = {}
        links: list = []
        for index, candidate in enumerate(candidates):
            register_location(
                yanqu, candidate["original_relative_path"], "original", blobs, locations
            )
            link_blob(
                locations[candidate["original_relative_path"]]["blob_sha256"],
                "ocr_poster",
                blobs,
                locations,
                links,
                source_record=f"YANQU-{candidate['csv_row']}",
            )
        report = counts(blobs, locations, links)
        self.assertEqual(report["file_locations"], 20)
        self.assertEqual(report["unique_blobs"], 20)
        self.assertEqual(report["links"], 20)
        self.assertEqual(report["missing_locations"], 0)

    def test_hardlink_two_locations_one_blob(self) -> None:
        register_location(
            self.root, "originals/a.png", "original", self.blobs, self.locations
        )
        (self.root / "hardlink.png").hardlink_to(self.root / "originals" / "a.png")
        entry = register_location(
            self.root, "hardlink.png", "delivery", self.blobs, self.locations
        )
        same = register_location(
            self.root, "originals/a.png", "original", self.blobs, self.locations
        )
        self.assertEqual(entry["blob_sha256"], same["blob_sha256"])
        report = counts(self.blobs, self.locations, self.links)
        self.assertEqual(report["unique_blobs"], 1)
        self.assertEqual(report["file_locations"], 2)

    def test_corrupt_detected_on_recheck(self) -> None:
        register_location(
            self.root, "originals/a.png", "original", self.blobs, self.locations
        )
        digest = self.locations["originals/a.png"]["blob_sha256"]
        (self.root / "originals" / "a.png").write_bytes(b"corrupted!!")
        self.assertNotEqual(sha256_stream(self.root / "originals" / "a.png"), digest)


if __name__ == "__main__":
    unittest.main()
