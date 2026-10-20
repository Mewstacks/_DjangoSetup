from __future__ import annotations

import json

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient

from apps.observability import checks


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_doctor_reports_a_healthy_development_setup(capsys: pytest.CaptureFixture[str]) -> None:
    call_command("doctor", "--json")
    results = {r["name"]: r for r in json.loads(capsys.readouterr().out)}
    assert results["database"]["status"] == "ok"
    assert results["encryption"]["status"] == "ok"
    assert results["audit chain"]["status"] == "ok"
    assert results["flows"]["status"] == "info"
    assert not [r for r in results.values() if r["status"] == "fail"]


@pytest.mark.django_db
def test_doctor_strict_fails_on_warnings_and_always_on_failures() -> None:
    with (
        override_settings(DEBUG=False, ADMIN_ENABLED=True, ADMIN_ALLOWED_IPS=[]),
        pytest.raises(SystemExit),
    ):
        call_command("doctor", "--strict")


@pytest.mark.django_db
def test_doctor_flags_https_gaps_outside_development() -> None:
    with override_settings(DEBUG=False, SESSION_COOKIE_SECURE=False):
        result = checks.check_https()
    assert result.status == checks.FAIL and "SESSION_COOKIE_SECURE" in result.detail


@pytest.mark.django_db
def test_a_missing_worker_never_takes_the_web_tier_out_of_rotation() -> None:
    cache.clear()
    client = APIClient()
    with override_settings(TEMPORAL_ENABLED=True):
        response = client.get("/api/v1/health/ready/")
    assert response.status_code == 200
    assert response.data["checks"]["worker"] == "unknown"
    cache.set("flows:worker:heartbeat", 1.0, 60)  # an ancient heartbeat
    with override_settings(TEMPORAL_ENABLED=True):
        stale = client.get("/api/v1/health/ready/")
    assert stale.status_code == 200 and stale.data["checks"]["worker"] == "stale"


def test_otel_spans_scrub_the_query_string_and_logs_carry_trace_ids() -> None:
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry import trace
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from apps.common.logging import add_app_context
    from apps.observability import otel

    exporter = InMemorySpanExporter()
    otel.shutdown()
    assert otel.setup(span_exporter=exporter) is True
    try:
        from django.test import Client

        with override_settings(OTEL_TRACES_SAMPLE_RATIO=1.0):
            Client().get("/api/v1/actions/?token=secret-in-the-query&email=a@b.com")
        spans = exporter.get_finished_spans()
        rendered = json.dumps([dict(s.attributes or {}) for s in spans], default=str)
        assert "secret-in-the-query" not in rendered and "a@b.com" not in rendered

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("unit"):
            event = add_app_context(None, "info", {"event": "x"})
        assert len(event["trace_id"]) == 32 and len(event["span_id"]) == 16
    finally:
        otel.shutdown()
