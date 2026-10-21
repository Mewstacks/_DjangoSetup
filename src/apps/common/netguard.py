"""The only way application code makes outbound HTTP requests to a URL somebody else chose.

A URL that comes from a database or a form (a webhook endpoint, a callback, an image to fetch)
is a way for a user to make *this server* send a request from inside the perimeter. Cloud
metadata services answer on a link-local address to anyone who asks, internal admin panels
listen on private ranges, and a hostname can point to both a public and a private address.

So every call here:

* allows only ``https`` (``http`` only when ``NETGUARD_ALLOW_PRIVATE`` or ``DEBUG`` says this is
  development);
* resolves the name and refuses it unless *every* answer is a globally routable address (an
  allow-list, ``is_global``: a deny-list of "private" ranges misses carrier-grade NAT
  100.64.0.0/10, which includes the Alibaba metadata address, and tunnelled IPv6 forms);
* **connects to the address it validated** (the URL is rewritten to the IP, ``Host`` and the TLS
  server name keep the original name), which closes the gap between "checked" and "used" that
  DNS rebinding relies on;
* never follows redirects (a redirect is a second, unvalidated destination);
* ignores ``HTTP(S)_PROXY`` from the environment (a proxy would receive the pinned request and
  could be reached through names this module never validated);
* bounds time (a total deadline, not only per-read timeouts) and response size, and never
  decompresses what the other side sends.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx
from django.conf import settings

from apps.common.exceptions import DomainError

MAX_RESPONSE_BYTES = 64 * 1024
DEFAULT_TIMEOUT = 10.0
# Wall-clock ceiling for one call; a peer that drips a byte per read would otherwise hold a
# worker for as long as it likes.
TOTAL_DEADLINE = 20.0
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
USER_AGENT = "saas-platform-webhooks/1.0"


class BlockedAddress(DomainError):
    status = 422
    code = "blocked_address"


class DeliveryFailed(DomainError):
    status = 502
    code = "delivery_failed"


@dataclass(frozen=True, slots=True)
class HttpResult:
    status: int
    headers: dict[str, str]
    body: bytes


def _development() -> bool:
    return bool(settings.NETGUARD_ALLOW_PRIVATE or settings.DEBUG)


def _embedded_ipv4(address: ipaddress.IPv6Address) -> list[ipaddress.IPv4Address] | None:
    """The IPv4 addresses an IPv6 form tunnels to, or ``None`` for a native IPv6 address."""
    if address.ipv4_mapped is not None:
        return [address.ipv4_mapped]
    if address in _NAT64:
        return [ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)]
    if address.sixtofour is not None:
        return [address.sixtofour]
    if address.teredo is not None:
        return list(address.teredo)
    return None


def _is_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
    )


def _check_ip(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise BlockedAddress(f"Unreadable address: {value}") from exc
    if isinstance(address, ipaddress.IPv6Address):
        embedded = _embedded_ipv4(address)
        if embedded is not None:
            public = all(_is_public(inner) for inner in embedded)
            if not public and not settings.NETGUARD_ALLOW_PRIVATE:
                raise BlockedAddress("That address is internal and cannot be called.")
            # A mapped address is the IPv4 address in disguise; the others must be dialled as is.
            return str(embedded[0]) if address.ipv4_mapped is not None else str(address)
    if not _is_public(address) and not settings.NETGUARD_ALLOW_PRIVATE:
        raise BlockedAddress("That address is internal and cannot be called.")
    return str(address)


def resolve(host: str, port: int) -> list[str]:
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise BlockedAddress(f"The host {host!r} does not resolve.") from exc
    # Every answer has to be acceptable, not just the first one the client would pick.
    return [_check_ip(str(entry[4][0])) for entry in answers]


def validate_url(url: str) -> tuple[str, str, int]:
    """Return ``(scheme, host, port)`` if the URL may be called, else raise ``BlockedAddress``."""
    parsed = urlparse(url)
    scheme = parsed.scheme
    allowed = {"https"} | ({"http"} if _development() else set())
    if scheme not in allowed:
        raise BlockedAddress("Only https URLs are allowed.")
    if not parsed.hostname:
        raise BlockedAddress("The URL has no host.")
    if parsed.username or parsed.password:
        raise BlockedAddress("Credentials in the URL are not allowed.")
    port = parsed.port or (443 if scheme == "https" else 80)
    resolve(parsed.hostname, port)
    return scheme, parsed.hostname, port


def post(
    url: str,
    *,
    body: bytes,
    headers: dict[str, str],
    timeout: float = DEFAULT_TIMEOUT,
) -> HttpResult:
    """POST ``body`` to ``url`` under every rule above."""
    scheme, host, port = validate_url(url)
    ip = resolve(host, port)[0]
    parsed = urlparse(url)
    netloc_ip = f"[{ip}]" if ":" in ip else ip
    pinned = urlunparse((scheme, f"{netloc_ip}:{port}", parsed.path or "/", "", parsed.query, ""))
    sent = {
        **headers,
        "Host": host if port in (80, 443) else f"{host}:{port}",
        "User-Agent": USER_AGENT,
    }
    deadline = time.monotonic() + TOTAL_DEADLINE
    sent["Accept-Encoding"] = "identity"
    try:
        with (
            httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client,
            client.stream(
                "POST",
                pinned,
                content=body,
                headers=sent,
                extensions={"sni_hostname": host},
            ) as response,
        ):
            received = b""
            # iter_raw: the bytes as sent, so a compressed bomb cannot expand inside one chunk.
            for chunk in response.iter_raw():
                received += chunk
                if len(received) >= MAX_RESPONSE_BYTES:
                    break
                if time.monotonic() > deadline:
                    raise DeliveryFailed("The endpoint answered too slowly.")
            return HttpResult(
                status=response.status_code,
                headers={k.lower(): v for k, v in response.headers.items()},
                body=received[:MAX_RESPONSE_BYTES],
            )
    except httpx.HTTPError as exc:
        raise DeliveryFailed(f"The endpoint did not answer ({type(exc).__name__}).") from exc
