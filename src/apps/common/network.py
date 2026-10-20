from __future__ import annotations

import ipaddress
from functools import lru_cache

from django.conf import settings
from django.http import HttpRequest

_IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _parse_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _trusted_networks(entries: tuple[str, ...]) -> tuple[_IpNetwork, ...]:
    networks: list[_IpNetwork] = []
    for entry in entries:
        try:
            networks.append(ipaddress.ip_network(entry.strip(), strict=False))
        except ValueError:
            continue
    return tuple(networks)


def _is_trusted(value: str, networks: tuple[_IpNetwork, ...]) -> bool:
    try:
        ip = ipaddress.ip_address(value.strip())
    except ValueError:
        return False
    return any(ip in network for network in networks)


def client_ip(request: HttpRequest) -> str | None:
    """Return a validated client IP, trusting X-Forwarded-For only through known proxies.

    Host-agnostic: this works behind Fly, Heroku, Render, Railway, an nginx/HAProxy edge,
    a cloud load balancer, or nothing at all. Configure whichever of these matches the
    deployment (both default to "trust nothing", so the direct peer is used):

    * ``TRUSTED_PROXY_IPS`` — CIDRs of the reverse proxies / load balancers in front of the
      app. The header is ignored unless the direct peer (``REMOTE_ADDR``) is one of them, so
      a caller that reaches the app directly cannot forge its address; the client is then the
      right-most forwarded entry that is not itself a trusted proxy. Prefer this when the
      proxy addresses are known.
    * ``TRUSTED_PROXY_COUNT`` — the number of trusted proxies in front of the app, for
      platforms whose router addresses are not fixed. The client is the Nth entry from the
      right of ``X-Forwarded-For``; the outermost trusted proxy overwrites what it appends,
      so entries the client tries to inject sit to the left of it and are never selected.

    ``TRUSTED_PROXY_IPS`` takes precedence when both are set.
    """

    remote_addr = request.META.get("REMOTE_ADDR")
    forwarded = request.headers.get("X-Forwarded-For", "")
    parts = [part.strip() for part in forwarded.split(",") if part.strip()]

    networks = _trusted_networks(tuple(getattr(settings, "TRUSTED_PROXY_IPS", ()) or ()))
    if networks:
        if parts and remote_addr and _is_trusted(remote_addr, networks):
            for candidate in reversed(parts):
                if not _is_trusted(candidate, networks):
                    resolved = _parse_ip(candidate)
                    if resolved is not None:
                        return resolved
        # Peer is not a trusted proxy, or every hop was trusted: fall back to the peer.
        return _parse_ip(remote_addr)

    proxy_count = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    if proxy_count > 0 and len(parts) >= proxy_count:
        resolved = _parse_ip(parts[-proxy_count])
        if resolved is not None:
            return resolved

    return _parse_ip(remote_addr)
