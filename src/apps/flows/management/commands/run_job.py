"""Run a job by name - the cron / Kubernetes CronJob entry point when Temporal is off."""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.common.exceptions import NotFound
from apps.flows.declare import JOBS
from apps.flows.jobs_runtime import execute_job
from apps.flows.registry import autodiscover


class Command(BaseCommand):
    help = "Run one job by name, or list them. Exit code 1 on failure so cron can alert."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("name", nargs="?")
        parser.add_argument("--list", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        autodiscover()
        if options["list"] or not options["name"]:
            for spec in sorted(JOBS.values(), key=lambda s: s.name):
                self.stdout.write(f"{spec.name:36} {spec.schedule or '(manual)'}")
            return
        try:
            result = execute_job(options["name"])
        except NotFound as error:
            raise CommandError(str(error.detail)) from error
        self.stdout.write(json.dumps(result, default=str))
