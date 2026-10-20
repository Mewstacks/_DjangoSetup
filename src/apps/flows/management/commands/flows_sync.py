"""Create or update Temporal Schedules from the jobs that declare a cron expression."""

from __future__ import annotations

import asyncio
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.flows.declare import JOBS
from apps.flows.registry import autodiscover


class Command(BaseCommand):
    help = "Sync Temporal Schedules with the jobs declared in code (idempotent)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--prune", action="store_true", help="Delete schedules without a job")
        parser.add_argument("--list", action="store_true", help="Only print what would exist")

    def handle(self, *args: Any, **options: Any) -> None:
        autodiscover()
        if options["list"]:
            for spec in sorted(JOBS.values(), key=lambda s: s.name):
                self.stdout.write(f"{spec.name:36} {spec.schedule or '(manual)'}")
            return
        if not settings.TEMPORAL_ENABLED:
            raise CommandError("TEMPORAL_ENABLED is false; use cron + `manage.py run_job`.")
        from apps.flows.runner import connect_client
        from apps.flows.schedules import sync_schedules

        async def go() -> dict[str, list[str]]:
            return await sync_schedules(await connect_client(), prune=options["prune"])

        report = asyncio.run(go())
        for verb, ids in report.items():
            for schedule_id in ids:
                self.stdout.write(f"{verb}: {schedule_id}")
        self.stdout.write("schedules in sync")
