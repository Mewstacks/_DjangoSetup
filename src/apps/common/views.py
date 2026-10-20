from __future__ import annotations

import time

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

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
    return checks


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
                "checks": serializers.DictField(
                    child=serializers.CharField(),
                ),
            },
        )
    )
    def get(self, request: object) -> Response:
        checks = readiness_checks()
        healthy = all(result == "ok" for result in checks.values())
        return Response(
            {"status": "ok" if healthy else "degraded", "checks": checks},
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
