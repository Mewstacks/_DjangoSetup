from __future__ import annotations

import re
from typing import Any

import pytest
from allauth.account.models import EmailAddress
from allauth.mfa.adapter import get_adapter
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal import auth as totp_auth
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

BASE = "/api/v1/accounts/app/v1"
PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    cache.clear()


def post(client: APIClient, path: str, data: dict[str, Any], token: str = "") -> Any:
    extra = {"HTTP_X_SESSION_TOKEN": token} if token else {}
    return client.post(f"{BASE}{path}", data, format="json", **extra)


def code_from_mail() -> str:
    body = mail.outbox[-1].body
    match = re.search(r"\b([A-Z0-9]{4}-[A-Z0-9]{4})\b", body)
    assert match, body
    return match.group(1)


def test_signup_is_closed_by_default() -> None:
    response = post(APIClient(), "/auth/signup", {"email": "new@example.com", "password": PASSWORD})
    assert response.status_code == 403
    assert not User.objects.filter(email="new@example.com").exists()


@override_settings(SIGNUP_ENABLED=True)
def test_signup_needs_a_verified_address_before_any_session() -> None:
    client = APIClient()
    signup = post(client, "/auth/signup", {"email": "new@example.com", "password": PASSWORD})
    assert signup.status_code == 401  # pending: verify the address first
    pending = [f["id"] for f in signup.json()["data"]["flows"] if f.get("is_pending")]
    assert pending == ["verify_email"]
    assert not signup.json()["meta"]["is_authenticated"]
    token = signup.json()["meta"]["session_token"]
    assert client.get("/api/v1/auth/me/", HTTP_X_SESSION_TOKEN=token).status_code in (401, 403)

    verified = client.post(
        f"{BASE}/auth/email/verify",
        {"key": code_from_mail()},
        format="json",
        HTTP_X_SESSION_TOKEN=token,
    )
    assert verified.status_code == 200, verified.content
    token = verified.json()["meta"].get("session_token", token)
    me = client.get("/api/v1/auth/me/", HTTP_X_SESSION_TOKEN=token)
    assert me.status_code == 200 and me.json()["email"] == "new@example.com"
    assert EmailAddress.objects.get(email="new@example.com").verified


@override_settings(SIGNUP_ENABLED=True)
def test_signup_does_not_reveal_existing_addresses(user: User) -> None:
    fresh = post(APIClient(), "/auth/signup", {"email": "fresh@example.com", "password": PASSWORD})
    taken = post(APIClient(), "/auth/signup", {"email": user.email, "password": PASSWORD})
    assert fresh.status_code == taken.status_code == 401
    assert [f["id"] for f in fresh.json()["data"]["flows"]] == [
        f["id"] for f in taken.json()["data"]["flows"]
    ]


def test_login_returns_a_token_that_works_on_the_api(user: User) -> None:
    client = APIClient()
    response = post(client, "/auth/login", {"email": user.email, "password": PASSWORD})
    assert response.status_code == 200, response.content
    token = response.json()["meta"]["session_token"]
    assert client.get("/api/v1/auth/me/", HTTP_X_SESSION_TOKEN=token).status_code == 200
    assert client.get("/api/v1/auth/me/").status_code in (401, 403)


def test_unverified_users_cannot_use_the_legacy_login(user: User) -> None:
    EmailAddress.objects.filter(user=user).update(verified=False)
    client = APIClient(enforce_csrf_checks=False)
    response = client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "use_accounts_flow"


def enable_totp(user: User) -> str:
    secret = totp_auth.generate_totp_secret()
    Authenticator.objects.create(
        user=user,
        type=Authenticator.Type.TOTP,
        data={"secret": get_adapter().encrypt(secret)},
    )
    return secret


def test_mfa_cannot_be_skipped_through_the_legacy_login(user: User) -> None:
    enable_totp(user)
    client = APIClient()
    legacy = client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json"
    )
    assert legacy.status_code == 403 and legacy.json()["error"]["code"] == "use_accounts_flow"

    login = post(client, "/auth/login", {"email": user.email, "password": PASSWORD})
    assert login.status_code == 401
    pending = [f["id"] for f in login.json()["data"]["flows"] if f.get("is_pending")]
    assert pending == ["mfa_authenticate"]
    token = login.json()["meta"]["session_token"]
    assert client.get("/api/v1/auth/me/", HTTP_X_SESSION_TOKEN=token).status_code in (401, 403)


def test_totp_secrets_are_stored_encrypted(user: User) -> None:
    secret = totp_auth.generate_totp_secret()
    Authenticator.objects.create(
        user=user,
        type=Authenticator.Type.TOTP,
        data={"secret": get_adapter().encrypt(secret)},
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT data FROM mfa_authenticator")
        raw = str(cursor.fetchone()[0])
    assert secret not in raw and "enc:v2:" in raw
    assert get_adapter().decrypt(Authenticator.objects.get().data["secret"]) == secret


def test_password_reset_is_uniform_for_unknown_addresses(user: User) -> None:
    known = post(APIClient(), "/auth/password/request", {"email": user.email})
    unknown = post(APIClient(), "/auth/password/request", {"email": "ghost@example.com"})
    assert known.status_code == unknown.status_code
