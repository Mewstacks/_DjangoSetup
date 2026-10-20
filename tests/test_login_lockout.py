from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.security import axes_username


@pytest.mark.django_db
@override_settings(AXES_FAILURE_LIMIT=2, AXES_COOLOFF_TIME=timedelta(minutes=30))
def test_repeated_failures_return_429_and_not_a_plain_401(user: User) -> None:
    cache.clear()
    client = APIClient()
    payload = {"email": user.email, "password": "wrong-password"}

    responses = [client.post("/api/v1/auth/login/", payload, format="json") for _ in range(3)]

    assert responses[0].status_code == 401
    locked = responses[-1]
    assert locked.status_code == 429
    assert locked["Retry-After"] == "1800"
    assert user.email.encode() not in locked.content


@pytest.mark.django_db
@override_settings(AXES_FAILURE_LIMIT=2)
def test_lockout_is_scoped_to_the_attacked_account(user: User) -> None:
    cache.clear()
    client = APIClient()
    for _ in range(3):
        client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "wrong-password"},
            format="json",
        )

    bystander = User.objects.create_user("bystander@example.com", "another-strong-password")
    response = client.post(
        "/api/v1/auth/login/",
        {"email": bystander.email, "password": "wrong-password"},
        format="json",
    )
    # Same IP, different account: the lockout must not spill over.
    assert response.status_code == 401


def test_username_is_resolved_from_either_credential_key() -> None:
    assert axes_username(None, {"email": " User@Example.COM "}) == "user@example.com"
    assert axes_username(None, {"username": "person@example.com"}) == "person@example.com"
    assert axes_username(RequestFactory().post("/", {"email": "form@example.com"})) == (
        "form@example.com"
    )
    assert axes_username(None, {"password": "irrelevant"}) == ""
