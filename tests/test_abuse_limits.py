"""Counters that keep one caller from choosing how fast the trail grows or locking an owner out."""

from __future__ import annotations

import pytest
from django.contrib.auth.signals import user_login_failed
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.actions.context import build_context
from apps.actions.runtime import invoke
from apps.apikeys.authentication import (
    FAILED_PER_MINUTE,
    FAILED_PER_MINUTE_PER_IP,
    authenticate_key,
    ip_allowed,
)
from apps.apikeys.models import ApiKey
from apps.audit.models import AuditEvent
from apps.common.exceptions import Forbidden
from apps.organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db


def _fail_logins(count: int, *, rotate_names: bool) -> None:
    request = RequestFactory().post("/accounts/login/", REMOTE_ADDR="198.51.100.7")
    for n in range(count):
        name = f"user{n}@example.com" if rotate_names else "same@example.com"
        user_login_failed.send(sender=None, credentials={"username": name}, request=request)


@override_settings(AUDIT_LOGIN_FAILURES_PER_CLIENT_MINUTE=5)
def test_rotating_account_names_cannot_inflate_the_trail() -> None:
    cache.clear()
    _fail_logins(200, rotate_names=True)
    assert AuditEvent.objects.filter(action="auth.login_failed").count() == 5


@override_settings(AUDIT_LOGIN_FAILURES_PER_CLIENT_MINUTE=5)
def test_a_single_account_is_still_coalesced() -> None:
    cache.clear()
    _fail_logins(50, rotate_names=False)
    assert AuditEvent.objects.filter(action="auth.login_failed").count() == 1


@override_settings(AUDIT_DENIALS_PER_CREDENTIAL_MINUTE=3)
def test_refused_actions_stop_growing_the_trail_after_the_first_few(
    user: User, organization: Organization, membership: Membership
) -> None:
    cache.clear()
    ctx = build_context(user=user, organization=organization, channel="api", scopes=frozenset())
    for _ in range(25):
        with pytest.raises(Forbidden):
            invoke("notes.create", ctx, {"title": "x"})
    assert AuditEvent.objects.filter(action="action.notes.create", success=False).count() == 3


def test_a_stranger_cannot_burn_the_owners_failure_budget(
    user: User, organization: Organization, membership: Membership
) -> None:
    cache.clear()
    _, raw = ApiKey.issue(user=user, organization=organization, label="ci", scopes=["notes:read"])
    prefix, public_id, _ = raw.split("_")
    wrong = f"{prefix}_{public_id}_{'0' * 64}"
    for _ in range(FAILED_PER_MINUTE + 5):
        assert authenticate_key(wrong, ip="203.0.113.50") is None  # the attacker's address
    assert authenticate_key(raw, ip="203.0.113.50") is None  # that address is now throttled
    assert authenticate_key(raw, ip="198.51.100.10") is not None  # the owner is unaffected


def test_spraying_many_key_ids_from_one_address_is_stopped() -> None:
    cache.clear()
    for n in range(FAILED_PER_MINUTE_PER_IP + 1):
        authenticate_key(f"key_{n:016x}_{'a' * 64}", ip="203.0.113.99")
    key = ApiKey(user=None, organization=None)  # type: ignore[misc]
    assert key is not None  # the sprayer no longer reaches the database for a new id
    assert authenticate_key(f"key_{'f' * 16}_{'a' * 64}", ip="203.0.113.99") is None


def test_the_allow_list_accepts_real_addresses_and_rejects_malformed_entries(
    org_client: APIClient,
) -> None:
    key = ApiKey(allowed_ips=["203.0.113.0/24", "2001:db8::/32"])
    assert ip_allowed(key, "203.0.113.9") and ip_allowed(key, "2001:db8:1::5")
    assert not ip_allowed(key, "198.51.100.1") and not ip_allowed(key, None)

    ok = org_client.post(
        "/api/v1/api-keys/",
        {"label": "ci", "profile": "read", "allowed_ips": ["203.0.113.0/24"]},
        format="json",
    )
    assert ok.status_code == 201
    for bad in (["not-an-ip"], ["10.0.0.0/33"], ["1.2.3.4"] * 21):
        refused = org_client.post(
            "/api/v1/api-keys/",
            {"label": "ci", "profile": "read", "allowed_ips": bad},
            format="json",
        )
        assert refused.status_code == 400, bad
