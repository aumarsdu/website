"""Pin each TCP connection to a DNS result verified as public.

The original HTTP Host and TLS server_hostname are retained by httpcore.
This is a scope guard, not proxying, identity spoofing or IP rotation.
"""
import asyncio
import ipaddress
import socket

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend


class PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(self):
        self.backend = AutoBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        try:
            entries = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout=timeout)
        except TimeoutError as exc:
            raise httpcore.ConnectTimeout("DNS resolution timed out") from exc
        except OSError as exc:
            raise httpcore.ConnectError("DNS resolution failed") from exc
        addresses = list(dict.fromkeys(x[4][0] for x in entries))
        if not addresses or not all(ipaddress.ip_address(x).is_global for x in addresses):
            raise httpcore.ConnectError("DNS target is not exclusively public")
        # Numeric host is passed to the socket backend: no second domain lookup.
        return await self.backend.connect_tcp(addresses[0], port, timeout, local_address, socket_options)

    async def connect_unix_socket(self, *args, **kwargs):
        raise httpcore.ConnectError("Unix sockets excluded")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


def public_transport():
    transport = httpx.AsyncHTTPTransport(trust_env=False)
    # httpx does not expose the httpcore network_backend constructor parameter.
    # Covered by tests against the installed httpx/httpcore runtime.
    transport._pool._network_backend = PublicNetworkBackend()
    return transport
