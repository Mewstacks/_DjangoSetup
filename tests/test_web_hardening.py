"""Response headers, CORS scope, the CSP report sink and the error pages."""

from __future__ import annotations

import json
from typing import Any

import pytest
import structlog
from django.core.cache import cache
from django.test import Client, RequestFactory, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.common.middleware import AdminIPAllowlistMiddleware

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery-staple"


def test_every_response_carries_permissions_policy_and_corp() -> None:
    response = Client().get("/api/v1/health/live/")
    assert "camera=()" in response["Permissions-Policy"]
    assert response["Cross-Origin-Resource-Policy"] == "same-origin"
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
    csp = response["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "report-uri /api/v1/csp-report/" in csp


@override_settings(CORS_ALLOWED_ORIGINS=["https://spa.example.test"])
def test_cors_covers_the_api_only_and_allows_the_headers_clients_send() -> None:
    from corsheaders.conf import conf  # noqa: F401  (settings are read per request)

    origin = {"HTTP_ORIGIN": "https://spa.example.test"}
    api = Client().options(
        "/api/v1/actions/",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="idempotency-key,x-session-token",
        **origin,
    )
    assert api["Access-Control-Allow-Origin"] == "https://spa.example.test"
    allowed = api["Access-Control-Allow-Headers"].lower()
    assert "idempotency-key" in allowed and "x-session-token" in allowed
    page = Client().get("/accounts/login/", **origin)
    assert "Access-Control-Allow-Origin" not in page


def test_the_csp_report_sink_logs_origins_only_and_always_answers_204() -> None:
    cache.clear()
    report = {
        "csp-report": {
            "violated-directive": "script-src-elem",
            "blocked-uri": "https://evil.example/steal?token=abc123secret",
            "document-uri": "https://app.example.test/o/authorize/?code=zzz",
        }
    }
    with structlog.testing.capture_logs() as logs:
        response = Client().post(
            "/api/v1/csp-report/", json.dumps(report), content_type="application/csp-report"
        )
    assert response.status_code == 204
    entry = next(item for item in logs if item["event"] == "csp_violation")
    assert entry["blocked"] == "https://evil.example"
    assert entry["document"] == "https://app.example.test"
    assert "abc123secret" not in json.dumps(logs) and "zzz" not in json.dumps(logs)

    for body in ("not json", "[]", '{"csp-report": 5}', "x" * 20_000):
        assert (
            Client().post("/api/v1/csp-report/", body, content_type="text/plain").status_code == 204
        )
    assert Client().get("/api/v1/csp-report/").status_code == 405


def test_the_csp_report_sink_is_rate_limited() -> None:
    cache.clear()
    report = json.dumps({"csp-report": {"violated-directive": "img-src", "blocked-uri": "inline"}})
    with structlog.testing.capture_logs() as logs:
        for _ in range(80):
            Client().post("/api/v1/csp-report/", report, content_type="application/csp-report")
    assert len([item for item in logs if item["event"] == "csp_violation"]) == 30


def test_the_admin_without_a_trailing_slash_is_hidden_from_strangers() -> None:
    with override_settings(ADMIN_ALLOWED_IPS=["10.0.0.0/8"]):
        middleware = AdminIPAllowlistMiddleware(lambda request: pytest.fail("reached the view"))
        for path in ("/admin", "/admin/", "/admin/accounts/user/"):
            request = RequestFactory().get(path, REMOTE_ADDR="203.0.113.5")
            assert middleware(request).status_code == 404, path


def test_api_errors_are_json_and_html_pages_are_not() -> None:
    from apps.common import views

    request = RequestFactory().get("/api/v1/nowhere/")
    for response, code in ((views.not_found(request), 404), (views.server_error(request), 500)):
        assert response.status_code == code
        assert json.loads(response.content)["error"]["code"] in {"not_found", "server_error"}
    page = RequestFactory().get("/somewhere/")
    assert not views.server_error(page).content.startswith(b'{"error"')


def test_the_legacy_password_login_is_off_by_default_and_never_bypasses_the_new_flow(
    user: User,
) -> None:
    body: dict[str, Any] = {"email": user.email, "password": PASSWORD}
    with override_settings(LEGACY_LOGIN_ENABLED=False):
        response = APIClient().post("/api/v1/auth/login/", body, format="json")
        assert response.status_code == 404
        assert "sessionid" not in response.cookies
    from config.settings import base

    assert base.LEGACY_LOGIN_ENABLED is False  # the shipped default


@override_settings(AXES_FAILURE_LIMIT=3)
def test_the_primary_login_flow_locks_out_too(user: User) -> None:
    """Lockout used to be tested only on the legacy endpoint."""
    cache.clear()
    base = "/api/v1/accounts/app/v1/auth/login"
    statuses = [
        APIClient().post(
            base, {"email": user.email, "password": "wrong-password-xyz"}, format="json"
        )
        for _ in range(6)
    ]
    assert statuses[0].status_code == 400  # allauth: invalid credentials
    assert any(r.status_code == 429 for r in statuses[3:])
    # a correct password does not get past an active lockout either
    locked = APIClient().post(base, {"email": user.email, "password": PASSWORD}, format="json")
    assert locked.status_code in (400, 403, 429)  # refused, whichever way allauth words it
    assert "session_token" not in json.dumps(locked.json().get("meta", {}))
