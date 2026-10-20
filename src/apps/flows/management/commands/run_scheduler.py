"""Run scheduled jobs from one process when Temporal is off (or a platform has no cron).

Run exactly one replica. A shared cache (Redis) additionally guards against a second copy
starting the same job in the same minute; with a per-process cache that guard is a no-op.
"""

from __future__ import annotations

import signal
import threading
from datetime import datetime
from typing import Any

import structlog
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.flows import cron
from apps.flows.declare import JOBS
from apps.flows.jobs_runtime import execute_job
from apps.flows.registry import autodiscover

logger = structlog.get_logger("apps.flows.scheduler")


def due_jobs(moment: datetime) -> list[str]:
    local = timezone.localtime(moment)
    return sorted(
        spec.name for spec in JOBS.values() if spec.schedule and cron.matches(spec.schedule, local)
    )


def tick(moment: datetime) -> dict[str, str]:
    """Run every job due in ``moment``'s minute once; return name -> ok|failed|skipped."""
    outcome: dict[str, str] = {}
    stamp = moment.strftime("%Y%m%d%H%M")
    for name in due_jobs(moment):
        if not cache.add(f"scheduler:{name}:{stamp}", 1, timeout=3600):
            outcome[name] = "skipped"
            continue
        try:
            execute_job(name)
            outcome[name] = "ok"
        except Exception:
            outcome[name] = "failed"  # execute_job already logged the traceback
    return outcome


class Command(BaseCommand):
    help = "Loop forever, running each job when its cron expression matches. One replica only."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--once", action="store_true", help="Run the current minute and exit")

    def handle(self, *args: Any, **options: Any) -> None:
        autodiscover()
        for spec in JOBS.values():
            if spec.schedule:
                cron.parse(spec.schedule)  # a bad expression stops the process at startup
        if options["once"]:
            self.stdout.write(str(tick(timezone.now())))
            return
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        logger.info("scheduler_started", jobs=len([s for s in JOBS.values() if s.schedule]))
        last = ""
        while not stop.is_set():
            now = timezone.now()
            minute = now.strftime("%Y%m%d%H%M")
            if minute != last:
                last = minute
                tick(now)
            stop.wait(max(1.0, 60 - now.second - now.microsecond / 1e6 + 0.5))
        logger.info("scheduler_stopped")
