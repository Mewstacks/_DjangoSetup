"""Run the Temporal worker: flows, jobs and tasks execute here."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run the Temporal worker for this project's task queue."

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.TEMPORAL_ENABLED:
            raise CommandError("TEMPORAL_ENABLED is false; there is nothing for a worker to do.")
        from apps.flows.worker import main

        main()
