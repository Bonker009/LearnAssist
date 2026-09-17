"""Fetch a user-supplied URL without letting it reach the internal network.

A student pastes a link; this service fetches it from inside the compose network,
where `postgres`, `rustfs`, `redis`, the AI service's own internal endpoints and the
host's Ollama are all one hop away. An unchecked fetch is therefore a server-side
request forgery hole: `http://rustfs:9000/lecture-uploads/<someone else's key>` or
`http://host.docker.internal:11434/api/delete` would be requested with this
service's network position.

The defence has three parts, all of which are needed:

1. Every address a hostname resolves to must be public. Checking the hostname string
   is useless -- `rustfs` and `127.0.0.1.nip.io` look harmless.
2. The connection goes to the address that was checked, not to the hostname. Letting
   the HTTP client resolve again would allow DNS rebinding: a name that resolves to a
   public IP for the check and to 10.0.0.5 a millisecond later for the request.
3. Redirects are followed by hand, re-running both checks on every hop, because a
   public page can 302 to an internal one.
"""

import asyncio
import ipaddress
import logging
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
_HTML_TYPES = ("text/html", "application/xhtml+xml", "text/plain")


class UnsafeUrl(ValueError):
    """The URL is malformed, not http(s), or points somewhere private."""


@dataclass
class FetchedPage:
    content: bytes
    final_url: str
    content_type: str


def is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    # An IPv4-mapped IPv6 address (::ffff:10.0.0.1) must be judged as the IPv4
    # address it really is, or it slips past every private-range check.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    # is_global excludes private, loopback, link-local (incl. cloud metadata at
    # 169.254.169.254), CGNAT, reserved and documentation ranges in one check.
    return ip.is_global and not ip.is_multicast


async def resolve_public(host: str, port: int) -> str:
    """Resolve `host` and return an address to connect to, or raise UnsafeUrl.

    All resolved addresses must be public, not just the first: a name with one public
    and one private record would otherwise be connectable to the private one.
    """
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
        addresses = [str(literal)]
    except ValueError:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise UnsafeUrl(f"Could not find the website {host}") from exc
        addresses = list(dict.fromkeys(info[4][0] for info in infos))

    if not addresses:
        raise UnsafeUrl(f"Could not find the website {host}")
    for address in addresses:
        if not is_public_address(address):
            logger.warning("Refused to fetch %s: resolves to non-public %s", host, address)
            raise UnsafeUrl("That link points to a private or local address")
    return addresses[0]


def _split(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise UnsafeUrl("Only http and https links can be added")
    if not parts.hostname:
        raise UnsafeUrl("That doesn't look like a web link")
    if parts.username or parts.password:
        raise UnsafeUrl("Links with a username or password aren't supported")
    try:
        port = parts.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeUrl("That link has an invalid port") from exc
    return scheme, parts.hostname, port


async def fetch_public_page(url: str) -> FetchedPage:
    """GET a public web page, following redirects safely, capped in size."""
    settings = get_settings()
    current = url

    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(settings.web_timeout_seconds),
        headers={
            "User-Agent": settings.web_user_agent,
            "Accept": "text/html,application/xhtml+xml",
        },
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            scheme, host, port = _split(current)
            address = await resolve_public(host, port)

            # Connect to the checked address. The Host header keeps virtual hosting
            # working, and sni_hostname makes TLS verify the certificate against the
            # real hostname rather than the bare IP.
            parts = urlsplit(current)
            netloc = f"[{address}]" if ":" in address else address
            if parts.port:
                netloc = f"{netloc}:{parts.port}"
            pinned = urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))

            request = client.build_request(
                "GET",
                pinned,
                headers={"Host": parts.netloc.rsplit("@", 1)[-1]},
                extensions={"sni_hostname": host} if scheme == "https" else {},
            )
            response = await client.send(request, stream=True)
            try:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise UnsafeUrl("The page redirected without saying where")
                    current = urljoin(current, location)
                    continue

                if response.status_code >= 400:
                    raise ValueError(f"The page returned HTTP {response.status_code}")

                content_type = response.headers.get("content-type", "").lower()
                if not content_type.startswith(_HTML_TYPES):
                    raise ValueError(
                        f"That link is not a web page ({content_type or 'unknown type'}). "
                        "Download the file and upload it instead."
                    )

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > settings.web_max_bytes:
                        raise ValueError("That page is too large to read")
                return FetchedPage(bytes(body), current, content_type)
            finally:
                await response.aclose()

    raise UnsafeUrl("The link redirected too many times")
