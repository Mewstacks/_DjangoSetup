from __future__ import annotations

from django.test import RequestFactory, override_settings

from apps.common.network import client_ip


def test_forwarded_header_is_ignored_without_trusted_proxy_config() -> None:
    request = RequestFactory().get(
        "/",
        HTTP_X_FORWARDED_FOR="203.0.113.9",
        REMOTE_ADDR="127.0.0.1",
    )
    assert client_ip(request) == "127.0.0.1"


@override_settings(TRUSTED_PROXY_COUNT=1)
def test_proxy_count_takes_the_client_from_the_right_of_the_chain() -> None:
    # A caller-injected address sits to the left of what the one trusted proxy appended.
    request = RequestFactory().get(
        "/",
        HTTP_X_FORWARDED_FOR="1.1.1.1, 203.0.113.9",
        REMOTE_ADDR="10.0.0.2",
    )
    assert client_ip(request) == "203.0.113.9"


@override_settings(TRUSTED_PROXY_COUNT=2)
def test_proxy_count_skips_the_configured_number_of_hops() -> None:
    request = RequestFactory().get(
        "/",
        HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.9",
        REMOTE_ADDR="10.0.0.2",
    )
    assert client_ip(request) == "203.0.113.9"


@override_settings(TRUSTED_PROXY_COUNT=2)
def test_proxy_count_falls_back_when_the_chain_is_too_short() -> None:
    request = RequestFactory().get(
        "/",
        HTTP_X_FORWARDED_FOR="203.0.113.9",
        REMOTE_ADDR="10.0.0.2",
    )
    assert client_ip(request) == "10.0.0.2"


@override_settings(TRUSTED_PROXY_IPS=["10.0.0.0/8"])
def test_trusted_cidrs_peel_proxies_and_return_the_client() -> None:
    request = RequestFactory().get(
        "/",
        HTTP_X_FORWARDED_FOR="203.0.113.9, 10.1.2.3",
        REMOTE_ADDR="10.0.0.2",
    )
    assert client_ip(request) == "203.0.113.9"


@override_settings(TRUSTED_PROXY_IPS=["10.0.0.0/8"])
def test_trusted_cidrs_ignore_the_header_when_the_peer_is_untrusted() -> None:
    # A caller reaching the app directly (peer not a trusted proxy) cannot forge its IP.
    request = RequestFactory().get(
        "/",
        HTTP_X_FORWARDED_FOR="203.0.113.9",
        REMOTE_ADDR="198.51.100.7",
    )
    assert client_ip(request) == "198.51.100.7"


@override_settings(TRUSTED_PROXY_COUNT=1)
def test_invalid_forwarded_value_falls_back_to_the_peer() -> None:
    request = RequestFactory().get(
        "/",
        HTTP_X_FORWARDED_FOR="not-an-ip",
        REMOTE_ADDR="2001:db8::1",
    )
    assert client_ip(request) == "2001:db8::1"
