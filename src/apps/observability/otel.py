"""OpenTelemetry, opt-in: traces and metrics over OTLP, correlated with the JSON logs.

Off unless ``OTEL_ENABLED`` is true; the packages live in the ``otel`` extra so a plain install
stays small. When on, Django requests, PostgreSQL queries and outbound HTTP become spans, the
Temporal client and worker add theirs (``TracingInterceptor``), and every log line carries
``trace_id`` / ``span_id`` (see ``apps.common.logging.add_app_context``).

Where the data goes is standard OpenTelemetry configuration: ``OTEL_EXPORTER_OTLP_ENDPOINT``,
``OTEL_EXPORTER_OTLP_HEADERS``, ``OTEL_EXPORTER_OTLP_PROTOCOL``. Nothing here sends anything
without an endpoint, and request URLs are reduced to their path before they become attributes
(query strings carry tokens and personal data).
"""

from __future__ import annotations

import os
from typing import Any

import structlog
from django.conf import settings

logger = structlog.get_logger("apps.observability")
_configured = False


def _scrub_request(span: Any, request: Any) -> None:
    if span is None or not span.is_recording():
        return
    path = getattr(request, "path", "")
    span.set_attribute("http.target", path)
    span.set_attribute("http.url", request.build_absolute_uri(path))
    span.set_attribute("url.query", "")


def setup(*, span_exporter: Any = None, metric_reader: Any = None) -> bool:
    """Configure providers and instrumentation once per process. Returns whether it ran."""
    global _configured
    if _configured:
        return False
    try:
        from opentelemetry import metrics, trace
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError:
        logger.error("otel_missing", hint="install the 'otel' extra: pip install '.[otel]'")
        return False

    resource = Resource.create(
        {
            "service.name": settings.OTEL_SERVICE_NAME,
            "deployment.environment": os.getenv("SENTRY_ENVIRONMENT", "production"),
        }
    )
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(settings.OTEL_TRACES_SAMPLE_RATIO)),
    )
    if span_exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    elif os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
    ):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    readers: list[Any] = []
    if metric_reader is not None:
        readers.append(metric_reader)
    elif os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"
    ):
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        readers.append(PeriodicExportingMetricReader(OTLPMetricExporter()))
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=readers))

    DjangoInstrumentor().instrument(
        request_hook=_scrub_request, excluded_urls="api/v1/health", is_sql_commentor_enabled=False
    )
    PsycopgInstrumentor().instrument(enable_commenter=False)
    HTTPXClientInstrumentor().instrument()
    _configured = True
    logger.info("otel_enabled", service=settings.OTEL_SERVICE_NAME)
    return True


def shutdown() -> None:
    global _configured
    if not _configured:
        return
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor

    DjangoInstrumentor().uninstrument()
    PsycopgInstrumentor().uninstrument()
    HTTPXClientInstrumentor().uninstrument()
    _configured = False
