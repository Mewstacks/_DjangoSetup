"""Regression tests for the second security review (see docs/en/security/review.md)."""

from __future__ import annotations

import time
from typing import Any, cast
from unittest import mock

import pytest
from allauth.account.internal.flows.login import AUTHENTICATION_METHODS_SESSION_KEY
from allauth.account.signals import password_reset
from allauth.mfa.signals import authenticator_removed
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from rest_framework.request import Request
from rest_framework.test import APIClient
from rest_framework.views import APIView

from apps.accounts.middleware import StaffMFARequiredMiddleware
from apps.accounts.models import User
from apps.apikeys.models import ApiKey
from apps.audit.models import AuditEvent
from apps.organizations.models import Membership, Organization
from apps.organizations.permissions import HasOrganizationContext

pytestmark = pytest.mark.django_db


def _staff(email: str, *, superuser: bool = False) -> User:
    return User.objects.create_user(
        email=email, password="correct-horse-battery-staple", is_staff=True, is_superuser=superuser
    )


# --- admin: no staff-to-superuser takeover ------------------------------------------------


def test_staff_cannot_see_edit_or_reset_a_superuser() -> None:
    boss = _staff("boss@example.com", superuser=True)
    clerk = _staff("clerk@example.com")
    model_admin = admin.site._registry[User]
    request = RequestFactory().get("/admin/accounts/user/")

    request.user = clerk
    visible = set(model_admin.get_queryset(request).values_list("email", flat=True))
    assert boss.email not in visible and clerk.email in visible
    assert model_admin.has_change_permission(request, boss) is False
    assert model_admin.has_delete_permission(request, boss) is False
    assert "email" in model_admin.get_readonly_fields(request, clerk)
    with pytest.raises(PermissionDenied):
        model_admin.user_change_password(request, str(clerk.pk))

    request.user = boss
    assert boss.email in set(model_admin.get_queryset(request).values_list("email", flat=True))
    assert "email" not in model_admin.get_readonly_fields(request, clerk)


# --- staff need a second factor for the admin ---------------------------------------------


def _through_staff_mfa(path: str, user: User, *, has_second_factor: bool) -> HttpResponse:
    middleware = StaffMFARequiredMiddleware(lambda request: HttpResponse("admin"))
    request = RequestFactory().get(path)
    request.user = user
    with (
        override_settings(STAFF_MFA_REQUIRED=True, ADMIN_ENABLED=True),
        mock.patch("apps.accounts.middleware.has_mfa", return_value=has_second_factor),
    ):
        return middleware(request)


def test_staff_without_an_authenticator_are_refused_the_admin() -> None:
    clerk = _staff("clerk@example.com")
    refused = _through_staff_mfa("/admin/", clerk, has_second_factor=False)
    assert refused.status_code == 403 and b"mfa_required" in refused.content
    assert _through_staff_mfa("/admin/", clerk, has_second_factor=True).status_code == 200
    # Only the admin is gated; the account pages where the factor is set up stay reachable.
    assert _through_staff_mfa("/accounts/2fa/", clerk, has_second_factor=False).status_code == 200


# --- owners and administrators need a second factor ---------------------------------------


def test_privileged_roles_need_a_second_factor_when_the_switch_is_on() -> None:
    request = cast(Request, RequestFactory().get("/"))
    request.user = User(email="o@example.com")  # type: ignore[assignment]
    view = APIView()
    permission = HasOrganizationContext()
    for role, needs in (
        (Membership.Role.OWNER, True),
        (Membership.Role.ADMIN, True),
        (Membership.Role.MEMBER, False),
        (Membership.Role.AUDITOR, False),
    ):
        request.organization_membership = Membership(role=role)  # type: ignore[attr-defined]
        with (
            override_settings(ORG_PRIVILEGED_MFA_REQUIRED=True),
            mock.patch("apps.accounts.middleware.has_mfa", return_value=False),
        ):
            assert permission.has_permission(request, view) is (not needs), role
        with (
            override_settings(ORG_PRIVILEGED_MFA_REQUIRED=True),
            mock.patch("apps.accounts.middleware.has_mfa", return_value=True),
        ):
            assert permission.has_permission(request, view) is True, role
    with override_settings(ORG_PRIVILEGED_MFA_REQUIRED=False):
        request.organization_membership = Membership(role=Membership.Role.OWNER)  # type: ignore[attr-defined]
        assert permission.has_permission(request, view) is True


# --- API keys: a stale session cannot mint a credential that outlives it ------------------


def _login_recorded(client: APIClient, *, seconds_ago: float) -> None:
    session = client.session
    session[AUTHENTICATION_METHODS_SESSION_KEY] = [
        {"method": "password", "at": time.time() - seconds_ago}
    ]
    session.save()


@override_settings(APIKEY_REQUIRE_RECENT_AUTH_SECONDS=900)
def test_minting_or_rotating_a_key_needs_a_recent_sign_in(org_client: APIClient) -> None:
    body = {"label": "ci", "profile": "read"}
    stale = org_client.post("/api/v1/api-keys/", body, format="json")
    assert stale.status_code == 403 and stale.json()["error"]["code"] == "reauthentication_required"

    _login_recorded(org_client, seconds_ago=3600)
    assert org_client.post("/api/v1/api-keys/", body, format="json").status_code == 403

    _login_recorded(org_client, seconds_ago=30)
    created = org_client.post("/api/v1/api-keys/", body, format="json")
    assert created.status_code == 201

    _login_recorded(org_client, seconds_ago=3600)
    assert org_client.post(f"/api/v1/api-keys/{created.json()['id']}/rotate/").status_code == 403


# --- a reset of the password or of the second factor revokes the owner's keys -------------


@pytest.mark.parametrize("signal", ["password", "mfa"])
def test_credential_resets_revoke_api_keys(
    user: User, organization: Organization, membership: Membership, signal: str
) -> None:
    key, _ = ApiKey.issue(user=user, organization=organization, label="ci", scopes=["notes:read"])
    other = User.objects.create_user(email="other@example.com", password="x" * 14)
    kept, _ = ApiKey.issue(
        user=other, organization=organization, label="kept", scopes=["notes:read"]
    )
    if signal == "password":
        password_reset.send(sender=User, request=None, user=user)
    else:
        authenticator_removed.send(sender=User, request=None, user=user, authenticator=None)
    key.refresh_from_db()
    kept.refresh_from_db()
    assert key.revoked_at is not None and kept.revoked_at is None
    event = AuditEvent.objects.get(action="apikey.revoked_on_reset")
    assert event.metadata["count"] == 1


@override_settings(APIKEY_REVOKE_ON_CREDENTIAL_RESET=False)
def test_revocation_on_reset_can_be_switched_off(
    user: User, organization: Organization, membership: Membership
) -> None:
    key, _ = ApiKey.issue(user=user, organization=organization, label="ci", scopes=["notes:read"])
    password_reset.send(sender=User, request=None, user=user)
    key.refresh_from_db()
    assert key.revoked_at is None


def _unused(*args: Any) -> None:  # keeps the typing import honest for editors
    return None


# --- OAuth: what may be registered, how tokens are stored ---------------------------------


@pytest.mark.parametrize(
    "metadata",
    [
        {"grant_types": ["client_credentials"], "redirect_uris": []},
        {"grant_types": ["implicit"], "redirect_uris": ["https://app.example/cb"]},
        {"redirect_uris": ["http://evil.example/cb"]},
        {"redirect_uris": ["https://app.example/*"]},
        {"redirect_uris": ["https://app.example/cb#frag"]},
        {"redirect_uris": ["javascript:alert(1)"]},
        {"redirect_uris": ["https://a.example/1"] * 6},
        {"redirect_uris": ["https://a.example/1"], "client_name": "x" * 101},
        ["not", "an", "object"],
    ],
)
def test_dynamic_registration_refuses_risky_metadata(metadata: Any) -> None:
    from apps.oauth.dcr import problem_with

    assert problem_with(metadata)


@pytest.mark.parametrize(
    "metadata",
    [
        {"redirect_uris": ["https://app.example/cb"], "grant_types": ["authorization_code"]},
        {"redirect_uris": ["http://127.0.0.1:7777/cb"]},
        {
            "redirect_uris": ["http://[::1]:7777/cb"],
            "grant_types": ["authorization_code", "refresh_token"],
        },
    ],
)
def test_dynamic_registration_accepts_what_mcp_clients_send(metadata: Any) -> None:
    from apps.oauth.dcr import problem_with

    assert problem_with(metadata) is None


@override_settings(OAUTH_DCR_ANONYMOUS=True)
def test_the_registration_endpoint_enforces_the_policy() -> None:
    import json

    from django.core.cache import cache
    from django.test import Client

    cache.clear()
    bad = {
        "client_name": "x",
        "redirect_uris": [],
        "grant_types": ["client_credentials"],
        "token_endpoint_auth_method": "client_secret_post",
    }
    reply = Client().post("/o/register/", json.dumps(bad), content_type="application/json")
    assert reply.status_code == 400 and reply.json()["error"] == "invalid_client_metadata"


def test_the_rfc_9700_gates_are_on() -> None:
    from django.conf import settings

    provider = settings.OAUTH2_PROVIDER
    gates = [name for name in provider if name.startswith("COMPLIANT_BCP_RFC9700_")]
    assert len(gates) >= 9 and all(provider[name] is True for name in gates)
    assert provider["REFRESH_TOKEN_REUSE_PROTECTION"] is True
    assert provider["DCR_REGISTRATION_TOKEN_EXPIRE_SECONDS"]  # never the year-9999 default
    assert provider["CIMD_ENABLED"] is False  # opt-in


def test_oauth_tokens_are_stored_as_a_checksum_and_still_verify(
    user: User, organization: Organization, membership: Membership
) -> None:
    from datetime import timedelta

    from django.utils import timezone
    from oauth2_provider.models import (
        get_access_token_model,
        get_application_model,
        set_token_value,
    )

    from apps.actions.mcp.verifier import _verify_oauth

    application = get_application_model().objects.create(
        name="c",
        client_type="public",
        authorization_grant_type="authorization-code",
        redirect_uris="http://127.0.0.1:9/cb",
    )
    token = get_access_token_model()(
        user=user,
        application=application,
        expires=timezone.now() + timedelta(hours=1),
        scope="notes:read",
        resource=["https://testserver/mcp"],
    )
    set_token_value(token, "raw-token-value")
    token.save()
    stored = get_access_token_model().objects.get(pk=token.pk)
    assert stored.token == "" and len(stored.token_checksum) == 64  # nothing replayable at rest
    assert _verify_oauth("raw-token-value", None) is not None
    assert _verify_oauth("raw-token-valuf", None) is None


# --- Temporal and the task bridge ---------------------------------------------------------


def test_production_temporal_must_be_sealed_and_authenticated() -> None:
    from django.core.exceptions import ImproperlyConfigured

    from config.settings import validators

    good = dict(
        enabled=True,
        payload_encryption=True,
        allow_plaintext=False,
        tls=True,
        api_key="",
        allow_insecure=False,
    )
    validators.check_temporal(**good)
    validators.check_temporal(**{**good, "tls": False, "allow_insecure": True})
    validators.check_temporal(**{**good, "tls": False, "api_key": "key"})
    validators.check_temporal(**{**good, "enabled": False, "tls": False})  # off: nothing to check
    for bad in (
        {"payload_encryption": False},
        {"allow_plaintext": True},
        {"tls": False},
    ):
        with pytest.raises(ImproperlyConfigured):
            validators.check_temporal(**{**good, **bad})


def test_the_task_bridge_runs_only_declared_tasks_under_allowed_prefixes() -> None:
    from temporalio.exceptions import ApplicationError

    from apps.flows.activities import run_task
    from apps.flows.sdk import TaskCall

    for path in ("os.system", "apps.common.encryption.encrypt_text", "builtins.print"):
        with pytest.raises(ApplicationError):
            run_task(TaskCall(path=path, args=[], kwargs={}))
