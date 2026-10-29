"""Shared test helpers.

The synthetic dataset under ``data/synthetic`` is the fixture set. It is
deliberately messy: it contains a genuine duration conflict, a near-duplicate
title, a purely promotional field, a partially stated date, and a document with
no external id.
"""

from __future__ import annotations

import logging
import unittest
from pathlib import Path

from research_facts.config import Settings
from research_facts.pipeline import IngestResult, ingest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC = PROJECT_ROOT / "data" / "synthetic"

PROFILE_FILE = SYNTHETIC / "web_profile.demo.json"
WEB_JSONL = SYNTHETIC / "web_domestic.jsonl"
POSTER_JSONL = SYNTHETIC / "poster_ocr.jsonl"
HANDBOOK_JSONL = SYNTHETIC / "handbook_pdf.jsonl"

ALL_INPUTS = [
    f"{WEB_JSONL}:web_json",
    f"{POSTER_JSONL}:poster_ocr",
    f"{HANDBOOK_JSONL}:handbook_pdf",
]


def build_settings(output_dir: Path, **overrides) -> Settings:
    params = {
        "output_dir": Path(output_dir),
        "inputs": list(ALL_INPUTS),
        "profile_files": [str(PROFILE_FILE)],
    }
    params.update(overrides)
    return Settings(**params)


def silence_logs() -> None:
    """Keep structured logs out of the test report.

    ``configure_logging`` attaches to stderr, and one CLI test is enough to
    make every later test print events.
    """
    logger = logging.getLogger("research_facts")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False


silence_logs()


class PipelineTestCase(unittest.TestCase):
    """Base class that runs the full pipeline once into a temp directory."""

    @classmethod
    def setUpClass(cls) -> None:
        import tempfile

        silence_logs()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._tmp.name) / "facts"
        cls.result: IngestResult = ingest(build_settings(cls.output_dir))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def record(self, fragment: str):
        matches = [item for item in self.result.records if fragment in item.record_key]
        self.assertTrue(matches, f"no record matching {fragment!r}")
        self.assertEqual(
            len(matches), 1, f"{fragment!r} matched {len(matches)} records: {[m.record_key for m in matches]}"
        )
        return matches[0]
