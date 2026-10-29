"""Typed errors and error classification for archive runs."""

from __future__ import annotations


class ArchiveError(Exception):
    """Base error for this project."""

    category = "unknown_error"


class ConfigError(ArchiveError):
    category = "config_error"


class ScopeError(ArchiveError):
    category = "scope_error"


class AuthError(ArchiveError):
    category = "http_401_unauthorized"


class ForbiddenError(ArchiveError):
    category = "http_403_forbidden"


class RateLimitedError(ArchiveError):
    category = "http_429_rate_limited"


class NotFoundError(ArchiveError):
    category = "http_404_not_found"


class ServerError(ArchiveError):
    category = "http_5xx_server_error"


class TimeoutArchiveError(ArchiveError):
    category = "timeout"


class ParseError(ArchiveError):
    category = "parse_error"


class SchemaValidationError(ArchiveError):
    category = "schema_validation_error"


class StorageError(ArchiveError):
    category = "storage_error"


def classify_http_status(status_code: int) -> str:
    if status_code == 401:
        return "http_401_unauthorized"
    if status_code == 403:
        return "http_403_forbidden"
    if status_code == 404:
        return "http_404_not_found"
    if status_code == 429:
        return "http_429_rate_limited"
    if 500 <= status_code <= 599:
        return "http_5xx_server_error"
    return "unknown_error"
