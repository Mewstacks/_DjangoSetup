from __future__ import annotations

from django.apps import AppConfig


class FlowsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.flows"

    def ready(self) -> None:
        from apps.flows.registry import autodiscover

        autodiscover()
