"""Error taxonomy for this package.

This package performs **no network I/O**: it reads local exports produced by the
partner crawlers, which already own HTTP error handling, rate limiting, and
robots enforcement. So the categories here are the ones this package can
actually produce. Network categories stay in ``crawler_common.errors`` where
they belong.
"""

from __future__ import annotations


class FactPackageError(Exception):
    """Base class for every error raised by this package."""

    category = "unknown_error"


class InputError(FactPackageError):
    """Input file missing, unreadable, or structurally invalid."""

    category = "input_error"


class SchemaValidationError(FactPackageError):
    """A record failed validation against the canonical field schema."""

    category = "schema_validation_error"


class ParseError(FactPackageError):
    """A document could not be turned into extractable blocks."""

    category = "parse_error"


class StorageError(FactPackageError):
    """Output could not be written."""

    category = "storage_error"
