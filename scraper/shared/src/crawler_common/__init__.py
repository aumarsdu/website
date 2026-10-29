"""crawler_common — shared, compliance-first building blocks for the scraper projects.

The scraper workspace grew eight crawler projects from one template. This package
holds the cross-cutting logic they all re-implement: rate-limited fetching with
domain whitelists and robots.txt support, retries with safe error classification,
sensitive-header redaction, content digests, JSON/JSONL storage helpers, and
hard-link aware file placement.

New code should import from here; existing projects migrate module by module.
"""

from crawler_common.digest import file_digest, sha256_bytes, sha256_text
from crawler_common.errors import classify_http_error
from crawler_common.redact import redact_headers, redact_mapping
from crawler_common.storage import (
    append_jsonl,
    iter_jsonl,
    read_json,
    write_json,
    write_jsonl,
)

__all__ = [
    "append_jsonl",
    "classify_http_error",
    "file_digest",
    "iter_jsonl",
    "read_json",
    "redact_headers",
    "redact_mapping",
    "sha256_bytes",
    "sha256_text",
    "write_json",
    "write_jsonl",
]
