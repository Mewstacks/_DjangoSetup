"""The data-export link is a bearer secret: capped, absolute, and kept out of logs."""

from __future__ import annotations

import json
import logging

import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.common.logging import AccessLogScrubFilter, redact
from apps.organizations.models import Membership, Organization
from apps.privacy.models import DataSubjectRequest

pytestmark = pytest.mark.django_db


def _request_an_export(
    user: User, capture: object, client: APIClient | None = None
) -> tuple[APIClient, str]:
    client = client or APIClient()
    client.force_authenticate(user)
    with capture(execute=True):  # type: ignore[operator]
        created = client.post(
            "/api/v1/privacy/requests/", {"request_type": "access"}, format="json"
        )
    assert created.status_code == 201
    message = next(m for m in mail.outbox if "export" in m.subject.lower())
    return client, message.body.splitlines()[1].strip()


@override_settings(PUBLIC_URL="https://app.example.test")
def test_the_mailed_link_is_absolute_and_stops_after_the_download_cap(
    user: User,
    organization: Organization,
    membership: Membership,
    django_capture_on_commit_callbacks: object,
) -> None:
    client, link = _request_an_export(user, django_capture_on_commit_callbacks)
    assert link.startswith("https://app.example.test/api/v1/privacy/exports/")
    path = link.removeprefix("https://app.example.test")

    with override_settings(PRIVACY_EXPORT_MAX_DOWNLOADS=2):
        assert client.get(path).status_code == 200
        assert client.get(path).status_code == 200
        assert client.get(path).status_code == 404  # spent, though the TTL has not passed
    assert DataSubjectRequest.objects.get().export_downloads == 2


def test_without_a_public_url_the_link_stays_a_path(
    user: User,
    organization: Organization,
    membership: Membership,
    django_capture_on_commit_callbacks: object,
) -> None:
    _, link = _request_an_export(user, django_capture_on_commit_callbacks)
    assert link.startswith("/api/v1/privacy/exports/")


def test_the_token_never_reaches_a_log_line() -> None:
    token = "abc.DEF_ghi-123:signature_part"
    assert token not in redact(f"GET /api/v1/privacy/exports/{token}/ 200")
    assert "[REDACTED_LINK]" in redact(f"/api/v1/privacy/exports/{token}/")

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        "%s - %s %s HTTP/%s %s",
        ("10.0.0.1:5", "GET", f"/api/v1/privacy/exports/{token}/", "1.1", 200),
        None,
    )
    assert AccessLogScrubFilter().filter(record)
    assert token not in json.loads(record.msg)["message"]


def test_the_public_url_must_be_an_https_origin_in_production() -> None:
    from django.core.exceptions import ImproperlyConfigured

    from config.settings import validators

    validators.check_public_url("https://app.example.com")
    validators.check_public_url("https://app.example.com/")
    for bad in ("", "http://app.example.com", "https://app.example.com/path", "app.example.com"):
        with pytest.raises(ImproperlyConfigured):
            validators.check_public_url(bad)
