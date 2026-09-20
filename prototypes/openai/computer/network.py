"""HTTPS public reads only; validation is part of the actual DNS resolver.

No redirects, proxies, file URLs, credentials, custom ports, or private addresses.
Provider/LiveKit operator configuration is separate from this untrusted URL path.
"""

import ipaddress
import socket
from urllib.parse import urlsplit
import aiohttp
from aiohttp.resolver import ThreadedResolver


def public_url(url: str):
    p = urlsplit(url)
    if (
        p.scheme != "https"
        or not p.hostname
        or p.username
        or p.password
        or p.port not in (None, 443)
        or "\\" in url
        or len(url) > 2048
    ):
        raise ValueError("Nur öffentliche HTTPS-Adressen ohne Zugangsdaten sind erlaubt.")
    host = p.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
        raise ValueError("Lokale Ziele sind gesperrt.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return url
    if not address.is_global:
        raise ValueError("Private oder reservierte Adresse gesperrt.")
    return url


class PublicResolver(ThreadedResolver):
    async def resolve(self, host, port=0, family=socket.AF_INET):
        records = await super().resolve(host, port, family)
        if not records or any(not ipaddress.ip_address(r["host"]).is_global for r in records):
            raise ValueError("DNS-Ziel ist nicht öffentlich.")
        return records


async def fetch_public(url: str, max_bytes=256_000):
    public_url(url)
    connector = aiohttp.TCPConnector(resolver=PublicResolver(), use_dns_cache=False)
    async with aiohttp.ClientSession(
        connector=connector, trust_env=False, timeout=aiohttp.ClientTimeout(total=15)
    ) as client:
        async with client.get(url, allow_redirects=False) as response:
            if response.status != 200:
                raise ValueError("Quelle nicht direkt erreichbar; Redirects sind gesperrt.")
            if response.content_length and response.content_length > max_bytes:
                raise ValueError("Antwort zu groß.")
            content = bytearray()
            async for block in response.content.iter_chunked(8192):
                content.extend(block)
                if len(content) > max_bytes:
                    raise ValueError("Antwort zu groß.")
            return bytes(content).decode("utf-8", errors="replace")
