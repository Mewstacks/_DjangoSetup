"""Declaring flows and jobs (importable inside Temporal's workflow sandbox: no Django here).

* A **flow** is a Temporal workflow class (long-running, durable, signals, timers). Declaring
  it with ``@flow`` registers it with the worker and lets ``flows.start()`` find it. Because the
  platform must also work with Temporal switched off, a flow may carry a ``local`` function:
  the same business process written as plain Python, run inline by the local engine. A flow
  without one is *temporal-only* and starting it with Temporal off raises ``FlowsDisabled``.
* A **job** is a plain function run once (optionally on a cron schedule): pruning, sweeps,
  reminders. Temporal runs it through a generic workflow; the local engine and
  ``manage.py run_job`` call it directly, so cron or a Kubernetes CronJob can drive the same
  code when there is no Temporal.

Modules named ``workflows.py``, ``activities.py`` and ``jobs.py`` in any installed app are
imported at startup. ``workflows.py`` runs inside Temporal's sandbox: it must not import
Django models (put the work in an action or a job and call it).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class FlowSpec:
    name: str
    workflow: type | None
    input_model: type[BaseModel] | None
    local: Callable[[dict[str, Any]], dict[str, Any] | None] | None
    scope: str
    startable: bool
    description: str

    @property
    def portable(self) -> bool:
        """Runs on both engines."""
        return self.workflow is not None and self.local is not None


@dataclass(frozen=True, slots=True)
class JobSpec:
    name: str
    fn: Callable[[], dict[str, Any] | None]
    schedule: str | None
    timeout: timedelta
    description: str


FLOWS: dict[str, FlowSpec] = {}
JOBS: dict[str, JobSpec] = {}
ACTIVITIES: list[Callable[..., Any]] = []


def flow(
    name: str,
    *,
    input: type[BaseModel] | None = None,
    local: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
    scope: str = "flows:write",
    startable: bool = False,
) -> Callable[[type], type]:
    """Register a Temporal workflow class as the flow ``name``."""

    def decorator(cls: type) -> type:
        from temporalio import workflow

        if name in FLOWS:
            raise ValueError(f"Flow {name} is declared twice.")
        if not hasattr(cls, "__temporal_workflow_definition"):
            cls = workflow.defn(name=name)(cls)
        FLOWS[name] = FlowSpec(
            name=name,
            workflow=cls,
            input_model=input,
            local=local,
            scope=scope,
            startable=startable,
            description=(cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else "",
        )
        return cls

    return decorator


def local_flow(
    name: str,
    *,
    input: type[BaseModel] | None = None,
    scope: str = "flows:write",
    startable: bool = False,
) -> Callable[[Callable[[dict[str, Any]], dict[str, Any] | None]], Any]:
    """Register a flow that has no Temporal workflow: only the local implementation."""

    def decorator(fn: Callable[[dict[str, Any]], dict[str, Any] | None]) -> Any:
        if name in FLOWS:
            raise ValueError(f"Flow {name} is declared twice.")
        FLOWS[name] = FlowSpec(
            name=name,
            workflow=None,
            input_model=input,
            local=fn,
            scope=scope,
            startable=startable,
            description=(fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else "",
        )
        return fn

    return decorator


def job(
    name: str,
    *,
    schedule: str | None = None,
    timeout: timedelta = timedelta(minutes=10),
) -> Callable[[Callable[[], dict[str, Any] | None]], Callable[[], dict[str, Any] | None]]:
    """Register ``fn()`` as the job ``name``; ``schedule`` is a 5-field cron in UTC."""

    def decorator(
        fn: Callable[[], dict[str, Any] | None],
    ) -> Callable[[], dict[str, Any] | None]:
        if name in JOBS:
            raise ValueError(f"Job {name} is declared twice.")
        JOBS[name] = JobSpec(
            name=name,
            fn=fn,
            schedule=schedule,
            timeout=timeout,
            description=(fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else "",
        )
        return fn

    return decorator


def activity(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Register an extra Temporal activity (the generic ones are built in)."""
    ACTIVITIES.append(fn)
    return fn
