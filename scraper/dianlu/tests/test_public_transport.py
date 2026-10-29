import asyncio
import socket

import httpcore
import pytest

from dianedu_archiver.public_transport import PublicNetworkBackend


def test_tcp_backend_uses_verified_numeric_ip(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])
    backend = PublicNetworkBackend()
    calls = []
    class Delegate:
        async def connect_tcp(self, *args):
            calls.append(args)
            return "fixture-stream"
    backend.backend = Delegate()
    assert asyncio.run(backend.connect_tcp("public.example", 443)) == "fixture-stream"
    assert calls[0][0] == "8.8.8.8"


def test_tcp_backend_cannot_connect_to_private_dns_result(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(httpcore.ConnectError):
        asyncio.run(PublicNetworkBackend().connect_tcp("public.example", 443))
