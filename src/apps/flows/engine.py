"""Starting and following flows - on Temporal when enabled, inline otherwise.

``get_engine()`` is the only thing application code needs::

    from apps.flows.engine import get_engine
    run = get_engine().start("privacy.dsar", {"request_id": "..."}, organization=org, actor=user)

The two engines expose the same methods, but they are *not* equivalent, and pretending so would
be a trap. The local engine runs a flow's ``local`` function inline, in the calling process, and
records it in ``FlowRun``. It cannot give you: durable timers that survive a restart, queries,
child workflows, continue-as-new, cancellation of a running call, or exactly-once activities.
What it keeps is the portable subset - ``start``, ``result``, ``signal`` through an explicit
handler, ordered steps, deadlines checked by a periodic job - which is what the built-in flows
are written against. ``capabilities()`` states this in code so the docs are generated from it.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from typing import Any, Protocol

import structlog
from django.conf import settings
from django.utils import timezone

from apps.common.context import request_id_var
from apps.common.exceptions import Conflict, NotFound, Unavailable
from apps.flows.declare import FLOWS, FlowSpec
from apps.flows.models import FlowRun

logger = structlog.get_logger("apps.flows.engine")


class FlowsDisabled(Unavailable):
    code = "flows_unavailable"


class Engine(Protocol):
    name: str

    def start(
        self,
        flow: str,
        payload: dict[str, Any] | None = None,
        *,
        organization: Any = None,
        actor: Any = None,
        workflow_id: str | None = None,
        start_delay: timedelta | None = None,
    ) -> FlowRun: ...

    def refresh(self, run: FlowRun) -> FlowRun: ...
    def result(self, run: FlowRun, timeout: float = 30) -> Any: ...
    def signal(self, run: FlowRun, name: str, payload: Any = None) -> None: ...
    def cancel(self, run: FlowRun) -> FlowRun: ...


def _spec(flow: str) -> FlowSpec:
    spec = FLOWS.get(flow)
    if spec is None:
        raise NotFound(f"Unknown flow {flow!r}.")
    return spec


IDENTITY_KEYS = ("organization_id", "actor_id")


def _validated(
    spec: FlowSpec, payload: dict[str, Any] | None, organization: Any = None, actor: Any = None
) -> dict[str, Any]:
    """Validate the input and stamp the caller's identity onto it.

    Who a flow acts for comes from the arguments of ``start()`` - the authenticated caller -
    and always overwrites any ``organization_id`` / ``actor_id`` found in the payload. A flow
    that reads identity from its input would otherwise let whoever can start it choose whose
    tenant and user it runs as.
    """
    data = dict(payload or {})
    for key in IDENTITY_KEYS:
        data.pop(key, None)
    if organization is not None:
        data["organization_id"] = str(organization.pk)
    if actor is not None and getattr(actor, "pk", None) is not None:
        data["actor_id"] = str(actor.pk)
    if spec.input_model is None:
        return data
    return spec.input_model.model_validate(data).model_dump(mode="json")


def _new_run(
    spec: FlowSpec, engine: str, payload: dict[str, Any], organization: Any, actor: Any, wid: str
) -> FlowRun:
    return FlowRun.objects.create(
        flow=spec.name,
        engine=engine,
        organization=organization,
        actor=actor if getattr(actor, "is_authenticated", True) else None,
        workflow_id=wid,
        request_id=request_id_var.get() or "",
        input_json=json.dumps(payload, default=str),
    )


# --- local ------------------------------------------------------------------------------


class LocalEngine:
    name = "local"

    def start(
        self,
        flow: str,
        payload: dict[str, Any] | None = None,
        *,
        organization: Any = None,
        actor: Any = None,
        workflow_id: str | None = None,
        start_delay: timedelta | None = None,
    ) -> FlowRun:
        spec = _spec(flow)
        if spec.local is None:
            raise FlowsDisabled(
                f"Flow {flow!r} needs Temporal (TEMPORAL_ENABLED=true); it has no local form.",
                code="flow_needs_temporal",
            )
        if start_delay:
            raise FlowsDisabled(
                "Delayed starts need Temporal; schedule a job for the local engine instead.",
                code="delay_needs_temporal",
            )
        data = _validated(spec, payload, organization, actor)
        wid = workflow_id or f"{flow}:{uuid.uuid4()}"
        if (
            workflow_id
            and FlowRun.objects.filter(workflow_id=wid, status__in=("running",)).exists()
        ):
            raise Conflict("A run with this id is already in progress.", code="already_running")
        run = _new_run(spec, self.name, data, organization, actor, wid)
        run.status = FlowRun.Status.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at", "updated_at"])
        try:
            result = spec.local(data)
        except Exception as error:  # a failed flow is a recorded outcome, not a crash here
            logger.exception("local_flow_failed", flow=flow, run_id=str(run.pk))
            run.status = FlowRun.Status.FAILED
            run.error = f"{type(error).__name__}: {error}"[:500]
        else:
            run.status = FlowRun.Status.COMPLETED
            run.result_json = json.dumps(result, default=str) if result is not None else ""
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "result_json", "finished_at", "updated_at"])
        return run

    def refresh(self, run: FlowRun) -> FlowRun:
        run.refresh_from_db()
        return run

    def result(self, run: FlowRun, timeout: float = 30) -> Any:
        run.refresh_from_db()
        if run.status == FlowRun.Status.FAILED:
            raise Conflict(run.error or "The flow failed.", code="flow_failed")
        return json.loads(run.result_json) if run.result_json else None

    def signal(self, run: FlowRun, name: str, payload: Any = None) -> None:
        raise FlowsDisabled(
            "Signals need Temporal. The local engine runs flows to completion inline.",
            code="signal_needs_temporal",
        )

    def cancel(self, run: FlowRun) -> FlowRun:
        raise FlowsDisabled(
            "A local run finishes before start() returns; there is nothing to cancel.",
            code="cancel_needs_temporal",
        )


# --- temporal ---------------------------------------------------------------------------


class TemporalEngine:
    name = "temporal"

    def _handle(self, run: FlowRun) -> Any:
        from apps.flows.runner import runner

        async def get() -> Any:
            client = await runner.client()
            return client.get_workflow_handle(run.workflow_id)

        return runner.run(get)

    def start(
        self,
        flow: str,
        payload: dict[str, Any] | None = None,
        *,
        organization: Any = None,
        actor: Any = None,
        workflow_id: str | None = None,
        start_delay: timedelta | None = None,
    ) -> FlowRun:

        spec = _spec(flow)
        if spec.workflow is None:
            raise FlowsDisabled(f"Flow {flow!r} has no Temporal workflow.", code="no_workflow")
        data = _validated(spec, payload, organization, actor)
        wid = workflow_id or f"{flow}:{uuid.uuid4()}"
        run = _new_run(spec, self.name, data, organization, actor, wid)
        return self.launch(run, spec, data, start_delay)

    def launch(
        self, run: FlowRun, spec: FlowSpec, data: dict[str, Any], start_delay: timedelta | None
    ) -> FlowRun:
        """Start the workflow for an already-recorded run (the task backend defers this to
        ``on_commit`` so a workflow never starts before the data it refers to is committed)."""
        from apps.flows.runner import runner

        flow, wid = spec.name, run.workflow_id
        organization = run.organization
        argument: Any = spec.input_model.model_validate(data) if spec.input_model else data

        async def start() -> Any:
            client = await runner.client()
            return await client.start_workflow(
                flow,
                argument,
                id=wid,
                task_queue=settings.TEMPORAL_TASK_QUEUE,
                start_delay=start_delay,
                memo={"flow": flow, "organization_id": str(getattr(organization, "pk", ""))},
            )

        try:
            handle = runner.run(start)
        except Exception as error:
            run.status = FlowRun.Status.FAILED
            run.error = f"{type(error).__name__}: {error}"[:500]
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "error", "finished_at", "updated_at"])
            raise Unavailable(
                "Could not reach the workflow engine.", code="engine_unreachable"
            ) from error
        run.temporal_run_id = handle.result_run_id or ""
        run.status = FlowRun.Status.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["temporal_run_id", "status", "started_at", "updated_at"])
        return run

    def refresh(self, run: FlowRun) -> FlowRun:
        from temporalio.client import WorkflowExecutionStatus as S

        from apps.flows.runner import runner

        if run.is_finished:
            return run
        handle = self._handle(run)
        description = runner.run(handle.describe)
        mapping = {
            S.RUNNING: FlowRun.Status.RUNNING,
            S.COMPLETED: FlowRun.Status.COMPLETED,
            S.CANCELED: FlowRun.Status.CANCELLED,
            S.FAILED: FlowRun.Status.FAILED,
            S.TERMINATED: FlowRun.Status.CANCELLED,
            S.TIMED_OUT: FlowRun.Status.FAILED,
            S.CONTINUED_AS_NEW: FlowRun.Status.RUNNING,
        }
        new_status = mapping.get(description.status, FlowRun.Status.RUNNING)
        run.status = new_status
        if new_status != FlowRun.Status.RUNNING:
            run.finished_at = description.close_time or timezone.now()
        run.save(update_fields=["status", "finished_at", "updated_at"])
        return run

    def result(self, run: FlowRun, timeout: float = 30) -> Any:
        from apps.flows.runner import runner

        handle = self._handle(run)
        value = runner.run(handle.result, timeout=timeout)
        run.status = FlowRun.Status.COMPLETED
        run.result_json = json.dumps(value, default=str) if value is not None else ""
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "result_json", "finished_at", "updated_at"])
        return value

    def signal(self, run: FlowRun, name: str, payload: Any = None) -> None:
        from apps.flows.runner import runner

        handle = self._handle(run)

        async def send() -> None:
            if payload is None:
                await handle.signal(name)
            else:
                await handle.signal(name, payload)

        runner.run(send)

    def cancel(self, run: FlowRun) -> FlowRun:
        from apps.flows.runner import runner

        handle = self._handle(run)
        runner.run(handle.cancel)
        run.status = FlowRun.Status.CANCELLED
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at", "updated_at"])
        return run


# --- selection --------------------------------------------------------------------------

_local = LocalEngine()
_temporal = TemporalEngine()


def get_engine() -> Engine:
    return _temporal if settings.TEMPORAL_ENABLED else _local


def capabilities() -> list[dict[str, Any]]:
    """The honest comparison between engines, rendered into the docs from here."""
    rows = [
        ("Start a flow and read its result", True, True),
        ("Run on the caller's thread vs. in a worker process", "inline", "worker"),
        ("Automatic retries with backoff", False, True),
        ("Survives a process restart mid-flow", False, True),
        ("Durable timers and sleeps (hours to months)", False, True),
        ("Signals to a running flow", False, True),
        ("Queries, child workflows, continue-as-new", False, True),
        ("Cancel a running flow", False, True),
        ("Scheduled jobs", "cron / CronJob + manage.py run_job", "Temporal Schedules"),
        ("Visibility UI and history", False, True),
    ]
    return [{"capability": c, "local": loc, "temporal": tmp} for c, loc, tmp in rows]
