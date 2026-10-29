from __future__ import annotations


def classify_http_error(status_code: int) -> str:
    """Map an HTTP status onto the workspace-standard error taxonomy."""
    if status_code == 401:
        return "http_401_unauthorized"
    if status_code == 403:
        return "http_403_forbidden"
    if status_code == 404:
        return "http_404_not_found"
    if status_code == 429:
        return "http_429_rate_limited"
    if status_code >= 500:
        return "http_5xx_server_error"
    return "unknown_error"


# Statuses that are transient and safe to retry (never retry 401/403/404).
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
