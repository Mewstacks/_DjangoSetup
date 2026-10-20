from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.apikeys.authentication import FAILED_PER_MINUTE, authenticate_key
from apps.apikeys.models import ApiKey
from apps.audit.models import AuditEvent
from apps.examples.models import Note
from apps.organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db


def bearer(raw: str, **extra: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}", **extra)
    return client


@pytest.fixture
def key_pair(user: User, organization: Organization, membership: Membership) -> tuple[ApiKey, str]:
    return ApiKey.issue(
        user=user, organization=organization, label="ci", scopes=["notes:read", "notes:write"]
    )


def test_only_a_keyed_hash_of_the_secret_is_stored(key_pair: tuple[ApiKey, str]) -> None:
    key, raw = key_pair
    secret = raw.split("_")[2]
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM apikeys_apikey")
        assert secret not in repr(cursor.fetchall())
    assert key.secret_index != secret and len(key.secret_index) == 64


def test_a_key_works_without_an_organization_header(key_pair: tuple[ApiKey, str]) -> None:
    _, raw = key_pair
    client = bearer(raw)
    created = client.post("/api/v1/actions/notes.create/", {"title": "via key"}, format="json")
    assert created.status_code == 200
    listed = client.get("/api/v1/notes/")  # the classic CRUD viewset accepts the key too
    assert listed.status_code == 200 and listed.data["count"] == 1
    event = AuditEvent.objects.get(action="action.notes.create")
    assert event.metadata["credential"] == str(key_pair[0].pk)


def test_a_key_cannot_choose_another_organization(
    key_pair: tuple[ApiKey, str], other_org_client: APIClient
) -> None:
    other_org = Organization.objects.get(slug="globex")
    _, raw = key_pair
    client = bearer(raw, HTTP_X_ORGANIZATION_ID=str(other_org.id))
    client.post("/api/v1/actions/notes.create/", {"title": "mine"}, format="json")
    assert Note.objects.filter(organization=other_org).count() == 0
    assert Note.objects.filter(organization=key_pair[0].organization).count() == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda k: k.revoke(),
        lambda k: ApiKey.objects.filter(pk=k.pk).update(expires_at=timezone.now() - timedelta(1)),
    ],
    ids=["revoked", "expired"],
)
def test_revoked_and_expired_keys_are_a_generic_401(
    key_pair: tuple[ApiKey, str], mutate: object
) -> None:
    key, raw = key_pair
    mutate(key)  # type: ignore[operator]
    response = bearer(raw).get("/api/v1/actions/")
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"


def test_forged_and_malformed_keys_look_identical(key_pair: tuple[ApiKey, str]) -> None:
    _key, raw = key_pair
    prefix, public_id, _ = raw.split("_")
    wrong_secret = bearer(f"{prefix}_{public_id}_{'0' * 64}").get("/api/v1/actions/")
    unknown_id = bearer(f"{prefix}_{'f' * 16}_{'0' * 64}").get("/api/v1/actions/")
    assert wrong_secret.status_code == unknown_id.status_code == 401
    strip = lambda r: {k: v for k, v in r.data["error"].items() if k != "request_id"}  # noqa: E731
    assert strip(wrong_secret) == strip(unknown_id)


def test_guessing_a_secret_is_throttled_per_public_id(key_pair: tuple[ApiKey, str]) -> None:
    cache.clear()
    _key, raw = key_pair
    prefix, public_id, _ = raw.split("_")
    for _ in range(FAILED_PER_MINUTE):
        assert authenticate_key(f"{prefix}_{public_id}_{'1' * 64}") is None
    assert authenticate_key(raw) is None  # even the right secret waits out the window
    cache.clear()
    assert authenticate_key(raw) is not None


def test_demoting_the_owner_takes_effect_on_the_next_call(
    key_pair: tuple[ApiKey, str], membership: Membership
) -> None:
    _, raw = key_pair
    client = bearer(raw)
    assert (
        client.post("/api/v1/actions/notes.create/", {"title": "a"}, format="json").status_code
        == 200
    )
    Membership.objects.filter(pk=membership.pk).update(role=Membership.Role.AUDITOR)
    denied = client.post("/api/v1/actions/notes.create/", {"title": "b"}, format="json")
    assert denied.status_code == 403 and denied.data["error"]["code"] == "read_only_role"
    Membership.objects.filter(pk=membership.pk).update(is_active=False)
    assert client.get("/api/v1/actions/").status_code == 401


def test_a_key_is_refused_on_endpoints_that_declare_no_scope(key_pair: tuple[ApiKey, str]) -> None:
    """Default deny: a new endpoint is closed to keys until somebody decides what it needs."""
    _, raw = key_pair
    client = bearer(raw)
    for path in ("/api/v1/auth/me/", "/api/v1/privacy/consents/", "/api/v1/organizations/"):
        assert client.get(path).status_code == 403, path
    assert client.get("/api/v1/api-keys/").status_code in (401, 403)  # session-only


def test_scoped_key_cannot_write_through_the_crud_viewset(
    user: User, organization: Organization, membership: Membership
) -> None:
    _, raw = ApiKey.issue(user=user, organization=organization, label="ro", scopes=["notes:read"])
    client = bearer(raw)
    assert client.get("/api/v1/notes/").status_code == 200
    assert client.post("/api/v1/notes/", {"title": "x"}, format="json").status_code == 403


def test_ip_allowlist_is_enforced(
    user: User, organization: Organization, membership: Membership
) -> None:
    _, raw = ApiKey.issue(
        user=user, organization=organization, label="ip", scopes=["notes:read"],
        allowed_ips=["203.0.113.0/24"],
    )  # fmt: skip
    inside = bearer(raw, REMOTE_ADDR="203.0.113.9").get("/api/v1/actions/")
    outside = bearer(raw, REMOTE_ADDR="198.51.100.9").get("/api/v1/actions/")
    assert inside.status_code == 200 and outside.status_code == 401


def test_unknown_scopes_cannot_be_issued(user: User, organization: Organization) -> None:
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        ApiKey.issue(user=user, organization=organization, label="x", scopes=["nope:write"])


# --- management API (session only) -----------------------------------------------------


def test_create_list_rotate_and_revoke_through_the_api(
    org_client: APIClient, organization: Organization
) -> None:
    created = org_client.post(
        "/api/v1/api-keys/",
        {"label": "ci", "profile": "read", "expires_in_days": 30},
        format="json",
    )
    assert created.status_code == 201
    assert created["Cache-Control"] == "no-store"
    secret = created.data["secret"]
    assert created.data["scopes"] == ["notes:read"]
    assert "secret" not in org_client.get(f"/api/v1/api-keys/{created.data['id']}/").data
    assert bearer(secret).get("/api/v1/notes/").status_code == 200

    rotated = org_client.post(f"/api/v1/api-keys/{created.data['id']}/rotate/")
    assert rotated.status_code == 201 and rotated.data["secret"] != secret
    assert bearer(secret).get("/api/v1/notes/").status_code == 200  # overlap window
    assert bearer(rotated.data["secret"]).get("/api/v1/notes/").status_code == 200

    assert org_client.delete(f"/api/v1/api-keys/{rotated.data['id']}/").status_code == 204
    assert bearer(rotated.data["secret"]).get("/api/v1/notes/").status_code == 401
    events = set(AuditEvent.objects.values_list("action", flat=True))
    assert {"apikey.created", "apikey.rotated", "apikey.revoked"} <= events


def test_a_key_cannot_exceed_its_creators_role(
    org_client: APIClient, membership: Membership
) -> None:
    Membership.objects.filter(pk=membership.pk).update(role=Membership.Role.AUDITOR)
    denied = org_client.post(
        "/api/v1/api-keys/", {"label": "w", "scopes": ["notes:write"]}, format="json"
    )
    assert denied.status_code == 403
    ok = org_client.post("/api/v1/api-keys/", {"label": "r", "profile": "full"}, format="json")
    assert ok.status_code == 403  # auditors cannot create keys at all


def test_a_key_cannot_mint_keys(key_pair: tuple[ApiKey, str]) -> None:
    _, raw = key_pair
    response = bearer(raw).post(
        "/api/v1/api-keys/", {"label": "x", "profile": "full"}, format="json"
    )
    assert response.status_code in (401, 403)
    assert ApiKey.objects.count() == 1


def test_members_only_see_their_own_keys(
    org_client: APIClient, organization: Organization, membership: Membership
) -> None:
    colleague = User.objects.create_user("peer@example.com", "a-long-password-1234")
    Membership.objects.create(
        organization=organization, user=colleague, role=Membership.Role.MEMBER
    )
    ApiKey.issue(user=colleague, organization=organization, label="theirs", scopes=["notes:read"])
    assert org_client.get("/api/v1/api-keys/").data["count"] == 1  # owner sees everyone's
    Membership.objects.filter(pk=membership.pk).update(role=Membership.Role.MEMBER)
    assert org_client.get("/api/v1/api-keys/").data["count"] == 0


def test_an_admin_can_revoke_but_never_rotate_somebody_elses_key(
    org_client: APIClient, organization: Organization
) -> None:
    """Review finding: rotating returned a working secret that authenticated as the owner."""
    colleague = User.objects.create_user("owner-of-key@example.com", "a-long-password-1234")
    Membership.objects.create(
        organization=organization, user=colleague, role=Membership.Role.MEMBER
    )
    theirs, _ = ApiKey.issue(
        user=colleague, organization=organization, label="theirs", scopes=["notes:read"]
    )
    denied = org_client.post(f"/api/v1/api-keys/{theirs.pk}/rotate/")
    assert denied.status_code == 403 and denied.data["error"]["code"] == "not_key_owner"
    assert ApiKey.objects.filter(user=colleague).count() == 1
    assert org_client.delete(f"/api/v1/api-keys/{theirs.pk}/").status_code == 204
