from __future__ import annotations

from urllib.parse import urlsplit


def hostname_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def is_allowed_hostname(url: str, allowed_hostnames: frozenset[str] | set[str]) -> bool:
    """Exact-hostname whitelist check (subdomains must be listed explicitly)."""
    return hostname_of(url) in {host.lower() for host in allowed_hostnames}


def is_subdomain_allowed(url: str, allowed_domains: frozenset[str] | set[str]) -> bool:
    """Domain whitelist that also accepts subdomains of the listed domains."""
    host = hostname_of(url)
    return any(host == domain or host.endswith(f".{domain}") for domain in (d.lower() for d in allowed_domains))
