"""The outbound-request guard refuses everything that is not a public internet address."""

from __future__ import annotations

import socket
from typing import Any

import httpx
import pytest
from django.test import override_settings

from apps.common import netguard
from apps.common.netguard import BlockedAddress

BLOCKED = [
    "127.0.0.1",
    "10.0.0.5",
    "172.16.0.1",
    "192.168.1.1",
    "169.254.169.254",  # link-local cloud metadata
    "100.100.100.200",  # Alibaba metadata, inside carrier-grade NAT
    "100.64.0.1",  # CGNAT / Tailscale
    "198.18.0.1",  # benchmarking
    "224.0.0.1",  # multicast
    "240.0.0.1",  # reserved
    "0.0.0.0",  # noqa: S104 - the literal under test
    "::1",
    "fe80::1",
    "fc00::1",
    "2001:db8::1",
    "::7f00:1",  # IPv4-compatible loopback
    "::ffff:127.0.0.1",  # IPv4-mapped loopback
    "::ffff:169.254.169.254",
    "64:ff9b::7f00:1",  # NAT64 wrapping 127.0.0.1
    "64:ff9b::a9fe:a9fe",  # NAT64 wrapping the metadata address
    "2002:7f00:1::1",  # 6to4 wrapping 127.0.0.1
    "2002:a9fe:a9fe::1",  # 6to4 wrapping the metadata address
    "2001:0:4136:e378:8000:63bf:3fff:fdd2",  # Teredo
    "not-an-address",
]
ALLOWED = ["8.8.8.8", "1.1.1.1", "2606:4700::1111", "::ffff:8.8.8.8", "64:ff9b::808:808"]


@pytest.mark.parametrize("value", BLOCKED)
def test_internal_and_tunnelled_addresses_are_refused(value: str) -> None:
    with override_settings(NETGUARD_ALLOW_PRIVATE=False), pytest.raises(BlockedAddress):
        netguard._check_ip(value)


@pytest.mark.parametrize("value", ALLOWED)
def test_public_addresses_pass(value: str) -> None:
    with override_settings(NETGUARD_ALLOW_PRIVATE=False):
        assert netguard._check_ip(value)


def test_the_development_switch_allows_a_local_receiver() -> None:
    with override_settings(NETGUARD_ALLOW_PRIVATE=True):
        assert netguard._check_ip("127.0.0.1") == "127.0.0.1"


def test_every_answer_of_a_name_must_be_public(monkeypatch: pytest.MonkeyPatch) -> None:
    """A name with one public and one private record is the DNS-rebinding shape."""

    def answers(host: str, port: int, **kwargs: Any) -> list[tuple[Any, ...]]:
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.100.100.200", port)),
        ]

    monkeypatch.setattr(netguard.socket, "getaddrinfo", answers)
    with (
        override_settings(NETGUARD_ALLOW_PRIVATE=False, DEBUG=False),
        pytest.raises(BlockedAddress),
    ):
        netguard.validate_url("https://rebind.example.test/hook")


def test_credentials_in_the_url_and_plain_http_are_refused() -> None:
    with override_settings(NETGUARD_ALLOW_PRIVATE=False, DEBUG=False):
        for url in ("http://example.com/x", "https://user:pw@example.com/x", "ftp://example.com"):
            with pytest.raises(BlockedAddress):
                netguard.validate_url(url)


def test_the_client_ignores_proxy_environment_and_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    class Recorder:
        def __init__(self, **kwargs: Any) -> None:
            seen.update(kwargs)

        def __enter__(self) -> Recorder:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def stream(self, *args: Any, **kwargs: Any) -> Any:
            raise httpx.ConnectError("stop here")

    monkeypatch.setattr(netguard.httpx, "Client", Recorder)
    monkeypatch.setattr(netguard, "resolve", lambda host, port: ["93.184.216.34"])
    with (
        override_settings(NETGUARD_ALLOW_PRIVATE=False, DEBUG=False),
        pytest.raises(netguard.DeliveryFailed),
    ):
        netguard.post("https://example.com/hook", body=b"{}", headers={})
    assert seen["trust_env"] is False
    assert seen["follow_redirects"] is False
