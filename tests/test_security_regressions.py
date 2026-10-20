"""One test per finding of the baseline security audit (numbers refer to docs/security/review).

These pin behaviour that used to be wrong; each docstring says what the old failure was.
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from django.test import RequestFactory, override_settings
from rest_framework import exceptions as drf_exceptions

from apps.common import logging as app_logging
from apps.common.asgi import BodyLimitMiddleware
from apps.common.exceptions import api_exception_handler
from apps.common.network import client_ip, client_ip_bucket
from apps.common.sentry import before_send
from config.settings import validators

# --- #1 / #30: client IP ----------------------------------------------------------------


def test_proxy_must_be_declared_in_production() -> None:
    """#1: the shipped config trusted no proxy, so every user shared the proxy's IP."""
    with pytest.raises(ImproperlyConfigured):
        validators.check_proxy(proxy_ips=[], proxy_count=0, direct=False)
    validators.check_proxy(proxy_ips=[], proxy_count=1, direct=False)
    validators.check_proxy(proxy_ips=["10.0.0.0/8"], proxy_count=0, direct=False)
    validators.check_proxy(proxy_ips=[], proxy_count=0, direct=True)


@override_settings(TRUSTED_PROXY_IPS=["10.0.0.0/8"], TRUSTED_PROXY_COUNT=0)
def test_ipv4_mapped_peer_matches_ipv4_cidr() -> None:
    """#30: ``::ffff:10.0.0.1`` never matched ``10.0.0.0/8`` so forwarded headers were ignored."""
    from apps.common import network

    network._trusted_networks.cache_clear()
    request = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="203.0.113.9", REMOTE_ADDR="::ffff:10.0.0.1"
    )
    assert client_ip(request) == "203.0.113.9"


def test_ipv6_clients_share_a_bucket_per_64() -> None:
    """#5: a /64 gave an attacker 2**64 throttle and lockout buckets."""
    first = RequestFactory().get("/", REMOTE_ADDR="2001:db8:1:2::1")
    second = RequestFactory().get("/", REMOTE_ADDR="2001:db8:1:2:ffff::9")
    other = RequestFactory().get("/", REMOTE_ADDR="2001:db8:1:3::1")
    assert client_ip_bucket(first) == client_ip_bucket(second) == "2001:db8:1:2::/64"
    assert client_ip_bucket(other) != client_ip_bucket(first)
    v4 = RequestFactory().get("/", REMOTE_ADDR="198.51.100.7")
    assert client_ip_bucket(v4) == "198.51.100.7"


# --- #4: request body size --------------------------------------------------------------


def _run_asgi(app: object, scope: dict, chunks: list[bytes]) -> tuple[int, bytes, bool]:
    sent: list[dict] = []
    queue = list(chunks)
    reached_app = False

    async def inner(scope_, receive, send):
        nonlocal reached_app
        reached_app = True
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": body})

    async def receive():
        chunk = queue.pop(0)
        return {"type": "http.request", "body": chunk, "more_body": bool(queue)}

    async def send(message):
        sent.append(message)

    guarded = BodyLimitMiddleware(inner, max_bytes=10)
    asyncio.run(guarded(scope, receive, send))
    status = sent[0]["status"]
    return status, sent[-1].get("body", b""), reached_app


def test_declared_oversized_body_is_rejected_without_reading() -> None:
    """#4: DATA_UPLOAD_MAX_MEMORY_SIZE was never enforced for streamed JSON bodies."""
    scope = {"type": "http", "method": "POST", "headers": [(b"content-length", b"999")]}
    status, body, reached = _run_asgi(None, scope, [b"x"])
    assert status == 413 and not reached
    assert json.loads(body)["error"]["code"] == "payload_too_large"


def test_chunked_body_is_cut_off_at_the_limit_and_small_body_replays() -> None:
    scope = {"type": "http", "method": "POST", "headers": []}
    status, _, reached = _run_asgi(None, scope, [b"12345", b"67890", b"1"])
    assert status == 413 and not reached
    status, body, reached = _run_asgi(None, scope, [b"abc", b"def"])
    assert status == 200 and body == b"abcdef" and reached


# --- #7 / #8 / #22: production validators ----------------------------------------------


def test_database_requires_tls_or_an_explicit_opt_out() -> None:
    """#7: only sslmode=disable was rejected; prefer/allow/unset passed."""
    base = {"ENGINE": "django.db.backends.postgresql", "OPTIONS": {}}
    with pytest.raises(ImproperlyConfigured):
        validators.check_database(base, allow_insecure_transport=False)
    with pytest.raises(ImproperlyConfigured):
        validators.check_database(
            {**base, "OPTIONS": {"sslmode": "prefer"}}, allow_insecure_transport=False
        )
    validators.check_database(
        {**base, "OPTIONS": {"sslmode": "verify-full"}}, allow_insecure_transport=False
    )
    validators.check_database(base, allow_insecure_transport=True)


def test_redis_needs_tls_or_a_password() -> None:
    """#7: plain redis:// carried sessions, lockout counters and throttles in clear."""
    with pytest.raises(ImproperlyConfigured):
        validators.check_redis_url("redis://cache:6379/0", allow_insecure=False)
    validators.check_redis_url("rediss://cache:6379/0", allow_insecure=False)
    validators.check_redis_url("redis://:pw@cache:6379/0", allow_insecure=False)


def test_hosts_have_no_local_default_in_production() -> None:
    """#7: the emptiness check was dead code because base.py defaulted to localhost."""
    with pytest.raises(ImproperlyConfigured):
        validators.check_hosts([])
    with pytest.raises(ImproperlyConfigured):
        validators.check_hosts(["localhost"])
    with pytest.raises(ImproperlyConfigured):
        validators.check_hosts(["*.example.com"])
    validators.check_hosts(["app.example.com"])


@pytest.mark.parametrize(
    "value",
    [
        "REPLACE_WITH_AN_INDEPENDENT_RANDOM_SECRET",
        "local-only-change-me-never-use-in-production",
        "a" * 60,
        "short",
    ],
)
def test_placeholder_and_weak_secrets_are_rejected(value: str) -> None:
    """#8: the .env.example HMAC placeholder was 41 chars and passed the >=32 check."""
    with pytest.raises(ImproperlyConfigured):
        validators.check_secret("X", value, min_length=32)


def test_key_decoding_is_strict() -> None:
    """#8: urlsafe_b64decode silently dropped junk characters."""
    with pytest.raises(ImproperlyConfigured):
        validators.decode_key("k", "MDAw!!MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    with pytest.raises(ImproperlyConfigured):
        validators.decode_key("k", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")  # all zero bytes


def test_secrets_must_differ_from_each_other() -> None:
    with pytest.raises(ImproperlyConfigured):
        validators.check_distinct_secrets(A="same-value", B="same-value")


def test_origins_must_be_https_without_wildcards() -> None:
    """#22: http://, null and wildcard origins were accepted."""
    for bad in ("http://app.example.com", "null", "https://*.example.com", "*"):
        with pytest.raises(ImproperlyConfigured):
            validators.check_origins("X", [bad])
    validators.check_origins("X", ["https://app.example.com"])


def test_admin_is_hidden_from_addresses_outside_the_allowlist() -> None:
    """#16/#22: the admin could be enabled in production with no network restriction."""
    from apps.common.middleware import AdminIPAllowlistMiddleware

    def view(request):
        from django.http import HttpResponse

        return HttpResponse("admin")

    with override_settings(ADMIN_ALLOWED_IPS=["203.0.113.0/24"]):
        middleware = AdminIPAllowlistMiddleware(view)
        denied = middleware(RequestFactory().get("/admin/", REMOTE_ADDR="198.51.100.1"))
        allowed = middleware(RequestFactory().get("/admin/", REMOTE_ADDR="203.0.113.5"))
        elsewhere = middleware(RequestFactory().get("/api/v1/x", REMOTE_ADDR="198.51.100.1"))
    assert denied.status_code == 404
    assert allowed.status_code == 200
    assert elsewhere.status_code == 200


# --- #9: log redaction ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "leaked"),
    [
        ('{"password": "hunter2"}', "hunter2"),
        ("{'password': 'hunter2'}", "hunter2"),
        ("AWS_SECRET_ACCESS_KEY=abcd1234wxyz", "abcd1234wxyz"),
        ("api_key=sk-live-123", "sk-live-123"),
        ("Cookie: csrftoken=a1; sessionid=XYZ789", "XYZ789"),
        ("postgres://user:s3cretpw@db.internal/app", "s3cretpw"),
        ("cpf 123.456.789-09", "123.456.789-09"),
        ("cnpj 12.345.678/0001-95", "12.345.678/0001-95"),
        ("phone (11) 98765-4321", "98765-4321"),
        ("client 203.0.113.77 failed", "203.0.113.77"),
        ("mail joao@example.com", "joao@example.com"),
        ("jwt eyJhbGciOi.eyJzdWIiOiIx.c2ln", "eyJzdWIiOiIx"),
        ("DETAIL: Key (email)=(a@b.com) already exists", "a@b.com"),
    ],
)
def test_redaction_covers_the_shapes_that_used_to_leak(raw: str, leaked: str) -> None:
    assert leaked not in app_logging.redact(raw)


def test_structured_values_are_redacted_by_key_and_by_content() -> None:
    cleaned = app_logging.redact_value(
        {"user": {"email": "a@b.com", "password": "x", "note": "call 11 98765-4321"}, "n": 3}
    )
    assert cleaned["user"]["email"] == app_logging.REDACTED
    assert cleaned["user"]["password"] == app_logging.REDACTED
    assert "98765" not in cleaned["user"]["note"]
    assert cleaned["n"] == 3


def test_json_pipeline_redacts_exception_text_and_keeps_context() -> None:
    from apps.common.context import request_id_var

    handler = logging.StreamHandler()
    handler.setFormatter(app_logging.build_formatter())
    record = logging.LogRecord("t", logging.ERROR, __file__, 1, "failed for %s", ("a@b.com",), None)
    try:
        raise ValueError("DETAIL: Key (email)=(leak@b.com)")
    except ValueError:
        import sys

        record.exc_info = sys.exc_info()
    token = request_id_var.set("req-1")
    try:
        line = handler.format(record)
    finally:
        request_id_var.reset(token)
    payload = json.loads(line)
    assert "a@b.com" not in line and "leak@b.com" not in line
    assert payload["request_id"] == "req-1"
    assert payload["level"] == "error"


def test_access_log_drops_query_string_and_peer_address() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("203.0.113.5:4411", "GET", "/api/v1/x?token=abc&email=a@b.com", "1.1", 200),
        None,
    )
    app_logging.AccessLogScrubFilter().filter(record)
    line = record.getMessage()
    assert "abc" not in line and "a@b.com" not in line and "203.0.113.5" not in line
    assert json.loads(line)["message"] == "GET /api/v1/x 200"


# --- #10: Sentry ------------------------------------------------------------------------


def test_sentry_drops_client_address_headers_and_environment() -> None:
    event = {
        "request": {
            "headers": {"X-Forwarded-For": "203.0.113.1", "User-Agent": "UA", "Accept": "json"},
            "env": {"REMOTE_ADDR": "203.0.113.1"},
        }
    }
    cleaned = before_send(event, {})
    assert cleaned is not None
    request = cleaned["request"]
    assert "env" not in request
    assert request["headers"]["X-Forwarded-For"] == "[Filtered]"
    assert request["headers"]["User-Agent"] == "[Filtered]"
    assert request["headers"]["Accept"] == "json"


# --- #28 / #29: error envelope and request id -------------------------------------------


def test_django_validation_and_suspicious_operation_become_client_errors() -> None:
    """#28: ValidationError from model code and SuspiciousOperation surfaced as 500/HTML."""
    from django.core.exceptions import ValidationError

    response = api_exception_handler(ValidationError("nope"), {})
    assert response is not None and response.status_code == 400
    assert response.data["error"]["code"] == "invalid"
    response = api_exception_handler(SuspiciousOperation("secret detail"), {})
    assert response is not None and response.status_code == 400
    assert "secret detail" not in json.dumps(response.data)
    response = api_exception_handler(RecursionError(), {})
    assert response is not None and response.status_code == 400
    assert isinstance(drf_exceptions.ParseError("x"), drf_exceptions.APIException)


@pytest.mark.django_db
def test_request_id_is_server_minted_and_client_value_kept_apart() -> None:
    from rest_framework.test import APIClient

    response = APIClient().get("/api/v1/health/live/", HTTP_X_REQUEST_ID="attacker-chosen")
    assert response["X-Request-ID"] != "attacker-chosen"


# --- #25: caching -----------------------------------------------------------------------


@pytest.mark.django_db
def test_api_responses_are_no_store_and_vary_on_organization() -> None:
    from rest_framework.test import APIClient

    response = APIClient().get("/api/v1/health/live/")
    assert response["Cache-Control"] == "no-store"
    assert "X-Organization-ID" in response["Vary"]


def test_native_structlog_events_are_redacted_too() -> None:
    """Review finding: events from ``structlog.get_logger()`` skipped the redaction step."""
    import io

    import structlog

    from apps.common.logging import configure_structlog

    configure_structlog()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(app_logging.build_formatter())
    target = logging.getLogger("native-test")
    target.handlers = [handler]
    target.propagate = False
    target.setLevel(logging.INFO)
    structlog.get_logger("native-test").info(
        "login", email="joao@example.com", password="hunter2", note="cpf 123.456.789-09"
    )
    line = stream.getvalue()
    assert "joao@example.com" not in line
    assert "hunter2" not in line
    assert "123.456.789-09" not in line
    assert json.loads(line)["message"] == "login"


# --- #16 / #24 / #35: admin, MeView, slugs ----------------------------------------------


@pytest.mark.django_db
def test_staff_without_superuser_cannot_edit_privilege_fields_in_the_admin() -> None:
    """#16: change_user was enough to grant is_superuser or any permission."""
    from django.contrib.admin.sites import site

    from apps.accounts.models import User

    model_admin = site._registry[User]
    staff = User.objects.create_user(email="staff@example.com", password="x" * 14, is_staff=True)
    request = RequestFactory().get("/admin/")
    request.user = staff
    readonly = model_admin.get_readonly_fields(request)
    for field in ("is_superuser", "is_staff", "groups", "user_permissions"):
        assert field in readonly
    staff.is_superuser = True
    assert "is_superuser" not in model_admin.get_readonly_fields(request)


@pytest.mark.django_db
def test_dsar_and_incidents_cannot_be_deleted_in_the_admin() -> None:
    from django.contrib.admin.sites import site

    from apps.privacy.models import DataSubjectRequest, PersonalDataIncident

    request = RequestFactory().get("/admin/")
    for model in (DataSubjectRequest, PersonalDataIncident):
        assert site._registry[model].has_delete_permission(request) is False


@pytest.mark.django_db
def test_me_patch_does_not_rewrite_columns_it_did_not_change() -> None:
    """#24: PATCH used a bare save(), so a stale copy could undo a concurrent deactivation."""
    from rest_framework.test import APIClient

    from apps.accounts.models import User

    user = User.objects.create_user(email="me@example.com", password="x" * 14, full_name="Old")
    client = APIClient()
    client.force_authenticate(user)
    # Simulate the concurrent change another worker commits after this request loaded `user`.
    User.objects.filter(pk=user.pk).update(is_active=False)
    response = client.patch("/api/v1/auth/me/", {"full_name": "New"}, format="json")
    assert response.status_code == 200
    stored = User.objects.get(pk=user.pk)
    assert stored.full_name == "New"
    assert stored.is_active is False


@pytest.mark.django_db
@pytest.mark.parametrize("slug", ["admin", "api", "www", "MCP"])
def test_reserved_organization_slugs_are_refused(slug: str) -> None:
    """#35: tenants could claim slugs that collide with routes or hostnames."""
    from django.core.exceptions import ValidationError

    from apps.organizations.models import Organization

    with pytest.raises(ValidationError):
        Organization(name="X", slug=slug).full_clean()


@pytest.mark.django_db
def test_readiness_hides_dependency_detail_from_anonymous_callers() -> None:
    """#27: the public probe named which dependency was down."""
    from rest_framework.test import APIClient

    with override_settings(HEALTH_DETAIL_PUBLIC=False):
        response = APIClient().get("/api/v1/health/ready/")
    assert response.status_code == 200
    assert response.data == {"status": "ok"}
