from __future__ import annotations

from django.apps import AppConfig
from django.conf import settings


class ObservabilityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.observability"

    def ready(self) -> None:
        if settings.OTEL_ENABLED:
            from apps.observability.otel import setup

            setup()
