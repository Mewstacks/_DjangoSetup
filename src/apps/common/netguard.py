"""The only way application code makes outbound HTTP requests to a URL somebody else chose.

A URL that comes from a database or a form (a webhook endpoint, a callback, an image to fetch)
is a way for a user to make *this server* send a request from inside the perimeter. Cloud
metadata services answer on a link-local address to anyone who asks, internal admin panels
listen on private ranges, and a hostname can point to both a public and a private address.

So every call here:

* allows only ``https`` (``http`` only when ``NETGUARD_ALLOW_PRIVATE`` or ``DEBUG`` says this is
  development);
* resolves the name and refuses it unless *every* answer is a public address;
* **connects to the address it validated** (the URL is rewritten to the IP, ``Host`` and the TLS
  server name keep the original name), which closes the gap between "checked" and "used" that
  DNS rebinding relies on;
* never follows redirects (a redirect is a second, unvalidated destination);
* bounds time and response size.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx
from django.conf import settings

from apps.common.exceptions import DomainError

MAX_RESPONSE_BYTES = 64 * 1024
DEFAULT_TIMEOUT = 10.0
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


def _check_ip(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise BlockedAddress(f"Unreadable address: {value}") from exc
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    internal = (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
    if internal and not settings.NETGUARD_ALLOW_PRIVATE:
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
    try:
        with (
            httpx.Client(timeout=timeout, follow_redirects=False) as client,
            client.stream(
                "POST",
                pinned,
                content=body,
                headers=sent,
                extensions={"sni_hostname": host},
            ) as response,
        ):
            received = b""
            for chunk in response.iter_bytes():
                received += chunk
                if len(received) >= MAX_RESPONSE_BYTES:
                    break
            return HttpResult(
                status=response.status_code,
                headers={k.lower(): v for k, v in response.headers.items()},
                body=received[:MAX_RESPONSE_BYTES],
            )
    except httpx.HTTPError as exc:
        raise DeliveryFailed(f"The endpoint did not answer ({type(exc).__name__}).") from exc
