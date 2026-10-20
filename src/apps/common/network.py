from __future__ import annotations

import ipaddress
from functools import lru_cache

from django.conf import settings
from django.http import HttpRequest

_IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _normalize(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    # A dual-stack socket reports an IPv4 peer as ::ffff:a.b.c.d, which would never match an
    # IPv4 CIDR and would give the same client two different throttle buckets.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _parse_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(_normalize(ipaddress.ip_address(value.strip())))
    except ValueError:
        return None


def parse_trusted_networks(entries: tuple[str, ...] | list[str]) -> tuple[_IpNetwork, ...]:
    """Parse CIDR entries strictly; a typo must fail loudly instead of silently trusting less."""
    return tuple(ipaddress.ip_network(entry.strip(), strict=False) for entry in entries)


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
        ip = _normalize(ipaddress.ip_address(value.strip()))
    except ValueError:
        return False
    return any(ip in network for network in networks)


def client_ip(request: HttpRequest) -> str | None:
    """Return a validated client IP, trusting X-Forwarded-For only through known proxies.

    Host-agnostic: this works behind Fly, Heroku, Render, Railway, an nginx/HAProxy edge,
    a cloud load balancer, or nothing at all. Configure whichever of these matches the
    deployment (both default to "trust nothing", so the direct peer is used):

    Throttle and lockout buckets must use :func:`client_ip_bucket`, not this value.

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


def client_ip_bucket(request: HttpRequest) -> str | None:
    """The client IP reduced to the unit an attacker actually controls.

    An IPv6 subscriber normally receives a whole /64, so keying a throttle or a lockout on the
    full address lets one client rotate through 2**64 buckets. IPv4 stays per-address.
    """
    resolved = client_ip(request)
    if resolved is None:
        return None
    ip = ipaddress.ip_address(resolved)
    if isinstance(ip, ipaddress.IPv6Address):
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return resolved
