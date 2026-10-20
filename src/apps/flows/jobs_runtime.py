"""Running a job by name - shared by Temporal, the local engine, ``run_job`` and cron."""

from __future__ import annotations

import time
from typing import Any

import structlog

from apps.common.exceptions import NotFound
from apps.flows.declare import JOBS

logger = structlog.get_logger("apps.flows.jobs")


def execute_job(name: str) -> dict[str, Any]:
    """Run job ``name`` and return its (JSON-safe) result. Unknown jobs raise ``NotFound``."""
    spec = JOBS.get(name)
    if spec is None:
        raise NotFound(f"Unknown job {name!r}.")
    started = time.monotonic()
    try:
        result = spec.fn() or {}
    except Exception:
        logger.exception("job_failed", job=name)
        raise
    logger.info(
        "job_done", job=name, duration_ms=round((time.monotonic() - started) * 1000, 1), **result
    )
    return dict(result)
