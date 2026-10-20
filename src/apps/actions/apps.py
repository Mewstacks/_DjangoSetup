from __future__ import annotations

from django.apps import AppConfig


class ActionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.actions"

    def ready(self) -> None:
        from apps.actions.registry import autodiscover

        autodiscover()
