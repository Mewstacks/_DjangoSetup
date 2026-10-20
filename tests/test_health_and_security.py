from __future__ import annotations

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.common.sentry import before_send, traces_sampler


@pytest.mark.django_db
def test_health_endpoints_are_public_and_correlated() -> None:
    client = APIClient()
    live = client.get("/api/v1/health/live/", HTTP_X_REQUEST_ID="test-request-123")
    assert live.status_code == 200
    assert live["X-Request-ID"] == "test-request-123"

    ready = client.get("/api/v1/health/ready/")
    assert ready.status_code == 200
    assert ready.data["checks"] == {"database": "ok", "cache": "ok"}


def test_security_defaults_and_sentry_scrubbing() -> None:
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.CSRF_COOKIE_HTTPONLY is True
    assert settings.X_FRAME_OPTIONS == "DENY"
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "rest_framework.permissions.IsAuthenticated"
    ]

    event = {
        "user": {"email": "person@example.com", "ip_address": "203.0.113.1"},
        "request": {
            "data": {"password": "secret"},
            "query_string": "email=person@example.com",
            "cookies": {"sessionid": "secret"},
            "headers": {"Authorization": "Bearer secret", "Accept": "application/json"},
        },
        "extra": {
            "api_token": "secret",
            "safe_count": 2,
            "nested": {"email": "person@example.com"},
        },
        "message": "Failed for person@example.com",
    }
    cleaned = before_send(event, {})
    assert cleaned is not None
    assert "user" not in cleaned
    assert "data" not in cleaned["request"]
    assert "query_string" not in cleaned["request"]
    assert "cookies" not in cleaned["request"]
    assert cleaned["request"]["headers"]["Authorization"] == "[Filtered]"
    assert cleaned["extra"]["api_token"] == "[Filtered]"
    assert cleaned["extra"]["nested"]["email"] == "[Filtered]"
    assert cleaned["message"] == "Failed for [REDACTED_EMAIL]"
    assert traces_sampler({"transaction_context": {"name": "GET /api/v1/health/live/"}}) == 0
