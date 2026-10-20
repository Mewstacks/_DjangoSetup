from __future__ import annotations

from django.test import RequestFactory
from rest_framework.request import Request

from apps.common.throttling import IPAnonRateThrottle


def test_forwarded_header_cannot_forge_a_throttle_bucket() -> None:
    factory = RequestFactory()
    throttle = IPAnonRateThrottle()

    first = factory.get("/", HTTP_X_FORWARDED_FOR="203.0.113.7", REMOTE_ADDR="198.51.100.1")
    second = factory.get("/", HTTP_X_FORWARDED_FOR="203.0.113.8", REMOTE_ADDR="198.51.100.1")
    assert throttle.get_ident(first) == "198.51.100.1"
    assert throttle.get_ident(first) == throttle.get_ident(second)


def test_ident_is_read_through_the_underlying_request() -> None:
    http_request = RequestFactory().get("/", REMOTE_ADDR="198.51.100.2")
    assert IPAnonRateThrottle().get_ident(Request(http_request)) == "198.51.100.2"


def test_unparseable_addresses_collapse_into_one_bucket() -> None:
    request = RequestFactory().get("/", REMOTE_ADDR="not-an-ip")
    assert IPAnonRateThrottle().get_ident(request) == ""
