from __future__ import annotations

import contextlib
import json
import time
from urllib.parse import urlparse

import structlog
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.defaults import page_not_found
from django.views.defaults import server_error as default_server_error
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import error_body
from apps.common.network import client_ip_bucket

_readiness_result: tuple[float, dict[str, str]] | None = None


def _run_readiness_checks() -> dict[str, str]:
    checks: dict[str, str] = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"

    try:
        cache.set("health:ready", "ok", timeout=10)
        checks["cache"] = "ok" if cache.get("health:ready") == "ok" else "unavailable"
    except Exception:
        checks["cache"] = "unavailable"
    if settings.TEMPORAL_ENABLED:
        checks["worker"] = _worker_state()
    return checks


# Reported, but never a reason to take the web tier out of rotation: a stalled worker delays
# background work, it does not stop requests from being served.
INFORMATIONAL = {"worker"}


def _worker_state() -> str:
    try:
        beat = cache.get("flows:worker:heartbeat")
    except Exception:
        return "unknown"
    if beat is None:
        return "unknown"
    return "ok" if time.time() - float(beat) < 90 else "stale"


def readiness_checks() -> dict[str, str]:
    """Run the dependency probes, reusing a recent result within the same worker.

    The endpoint is public by design, so without memoisation every anonymous request
    would cost a database round trip and a cache write. A per-process TTL bounds that
    without introducing a throttle, which would itself depend on the cache being up.
    """

    global _readiness_result

    ttl = settings.HEALTH_READINESS_CACHE_SECONDS
    now = time.monotonic()
    cached = _readiness_result
    if ttl > 0 and cached is not None and now - cached[0] < ttl:
        return cached[1]

    checks = _run_readiness_checks()
    _readiness_result = (now, checks)
    return checks


class LivenessView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]
    throttle_classes: list[type] = []

    @extend_schema(
        responses=inline_serializer(
            name="Liveness",
            fields={"status": serializers.CharField()},
        )
    )
    def get(self, request: object) -> Response:
        return Response({"status": "ok"})


class ReadinessView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]
    throttle_classes: list[type] = []

    @extend_schema(
        responses=inline_serializer(
            name="Readiness",
            fields={
                "status": serializers.CharField(),
                "checks": serializers.DictField(child=serializers.CharField(), required=False),
            },
        )
    )
    def get(self, request: object) -> Response:
        checks = readiness_checks()
        healthy = all(r == "ok" for name, r in checks.items() if name not in INFORMATIONAL)
        body: dict[str, object] = {"status": "ok" if healthy else "degraded"}
        # Which dependency is down is reconnaissance for an anonymous caller; platform probes
        # only need the status code. Operators opt in with HEALTH_DETAIL_PUBLIC or use
        # `manage.py doctor`.
        if settings.HEALTH_DETAIL_PUBLIC:
            body["checks"] = checks
        return Response(
            body,
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# --- error pages ------------------------------------------------------------------------


def not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    """JSON for the API, Django's plain page for everything else."""
    if request.path.startswith("/api/"):
        return JsonResponse(error_body(404, "not_found", "Not found."), status=404)
    return page_not_found(request, exception or Http404())


def server_error(request: HttpRequest) -> HttpResponse:
    """A 500 carries no detail; the request id header (set by the middleware) is the handle."""
    if request.path.startswith("/api/"):
        return JsonResponse(error_body(500, "server_error", "Something went wrong."), status=500)
    return default_server_error(request)


# --- CSP violation sink -----------------------------------------------------------------

CSP_REPORT_MAX_BYTES = 8 * 1024
CSP_REPORT_PER_MINUTE = 30
csp_logger = structlog.get_logger("apps.csp")


def _origin_only(value: object) -> str:
    """Scheme and host of a reported URL: paths and queries carry tokens and identifiers."""
    parsed = urlparse(str(value or ""))
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"[:200]
    return str(value or "")[:40]  # "inline", "eval", "data", ...


@csrf_exempt
@require_POST
def csp_report(request: HttpRequest) -> HttpResponse:
    """Log a Content-Security-Policy violation. Always answers 204: a report is not a request
    the browser should retry, and the endpoint must reveal nothing."""
    bucket = client_ip_bucket(request) or ""
    key = f"csp:report:{bucket}:{int(time.time() // 60)}"
    over = False
    with contextlib.suppress(Exception):  # a cache outage must not turn a report into an error
        cache.add(key, 0, 120)
        over = int(cache.incr(key)) > CSP_REPORT_PER_MINUTE
    if over:
        return HttpResponse(status=204)
    if int(request.headers.get("Content-Length") or 0) > CSP_REPORT_MAX_BYTES:
        return HttpResponse(status=204)
    try:
        payload = json.loads(request.body[:CSP_REPORT_MAX_BYTES] or b"{}")
    except ValueError:
        return HttpResponse(status=204)
    reports = payload if isinstance(payload, list) else [payload]
    for item in reports[:5]:
        # Legacy `report-uri` wraps the body in {"csp-report": {...}}; the Reporting API sends
        # a list of {"type": "csp-violation", "body": {...}} with camelCase keys.
        body = item.get("csp-report") or item.get("body") or {} if isinstance(item, dict) else {}
        if not isinstance(body, dict):
            continue
        csp_logger.warning(
            "csp_violation",
            directive=str(body.get("violated-directive") or body.get("effectiveDirective") or "")[
                :60
            ],
            blocked=_origin_only(body.get("blocked-uri") or body.get("blockedURL")),
            document=_origin_only(body.get("document-uri") or body.get("documentURL")),
        )
    return HttpResponse(status=204)
