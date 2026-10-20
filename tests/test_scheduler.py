from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.core.cache import cache

from apps.flows import cron
from apps.flows.declare import JOBS, JobSpec
from apps.flows.management.commands import run_scheduler


def at(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


@pytest.mark.parametrize(
    ("expression", "moment", "expected"),
    [
        ("* * * * *", "2026-10-20 10:07", True),
        ("*/10 * * * *", "2026-10-20 10:20", True),
        ("*/10 * * * *", "2026-10-20 10:25", False),
        ("40 4 * * *", "2026-10-20 04:40", True),
        ("40 4 * * *", "2026-10-20 05:40", False),
        ("0 9 * * 1-5", "2026-10-19 09:00", True),  # Monday
        ("0 9 * * 1-5", "2026-10-18 09:00", False),  # Sunday
        ("0 9 * * 7", "2026-10-18 09:00", True),  # 7 is Sunday too
        ("0 0 1,15 * *", "2026-10-15 00:00", True),
        ("0 0 13 * 5", "2026-10-16 00:00", True),  # day-of-week OR day-of-month
        ("5-15/5 * * * *", "2026-10-20 10:10", True),
    ],
)
def test_cron_matching(expression: str, moment: str, expected: bool) -> None:
    assert cron.matches(expression, at(moment)) is expected


@pytest.mark.parametrize("bad", ["", "* * * *", "61 * * * *", "*/0 * * * *", "a * * * *"])
def test_bad_expressions_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        cron.parse(bad)


def test_tick_runs_due_jobs_once_per_minute(settings: Any) -> None:
    settings.TIME_ZONE = "UTC"
    calls: list[str] = []
    saved = dict(JOBS)
    JOBS.clear()
    try:
        for name, schedule in (("a.due", "*/5 * * * *"), ("b.later", "0 3 * * *")):
            JOBS[name] = JobSpec(
                name=name,
                fn=lambda name=name: calls.append(name) or {},  # type: ignore[misc]
                schedule=schedule,
                timeout=timedelta(minutes=1),
                description="",
            )
        cache.clear()
        moment = at("2026-10-20 10:05")
        assert run_scheduler.tick(moment) == {"a.due": "ok"}
        assert run_scheduler.tick(moment) == {"a.due": "skipped"}  # same minute, same job
        assert calls == ["a.due"]
    finally:
        JOBS.clear()
        JOBS.update(saved)
