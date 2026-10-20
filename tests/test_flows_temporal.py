"""Flows on a real Temporal server (the SDK's time-skipping test server, downloaded on first use).

Run with the rest of the suite or alone: ``pytest -m temporal``. These prove what the local
engine cannot: that payloads in workflow history are sealed, that the request id survives the
trip into an activity, that a refusal is not retried, that timers can be fast-forwarded and
that the workflow code replays deterministically.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.tasks import task
from django.test import override_settings
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer

import flow_fixtures
from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.common.context import request_id_var
from apps.examples.models import Note
from apps.flows.converter import build_data_converter
from apps.flows.engine import TemporalEngine
from apps.flows.interceptors import PlatformInterceptor
from apps.flows.models import FlowRun
from apps.flows.runner import connect_client, runner
from apps.flows.worker import build_worker
from apps.organizations.models import Membership, Organization

pytestmark = [pytest.mark.temporal, pytest.mark.django_db(transaction=True)]
SECRET = "123.456.789-09 joao@example.com"


@pytest.fixture
def temporal() -> Iterator[WorkflowEnvironment]:
    converter = build_data_converter()

    async def boot() -> tuple[WorkflowEnvironment, Any, asyncio.Future[None]]:
        env = await WorkflowEnvironment.start_time_skipping(
            data_converter=converter,
            interceptors=[PlatformInterceptor(converter.payload_converter)],
        )
        worker = build_worker(env.client)
        return env, worker, asyncio.ensure_future(worker.run())

    env, worker, running = runner.run(boot, timeout=240)

    async def factory() -> Any:
        return env.client

    runner.use_client_factory(factory)
    with override_settings(TEMPORAL_ENABLED=True):
        yield env

    async def stop() -> None:
        await worker.shutdown()
        await running
        await env.shutdown()

    runner.run(stop, timeout=60)
    runner.use_client_factory(connect_client)


def start_greet(user: User, organization: Organization, **extra: str) -> FlowRun:
    return TemporalEngine().start(
        "test.greet",
        {"title": "durable", **extra},
        organization=organization,
        actor=user,
    )


def test_a_flow_runs_on_temporal_and_its_history_holds_no_plaintext(
    temporal: WorkflowEnvironment, user: User, organization: Organization, membership: Membership
) -> None:
    run = start_greet(user, organization, secret=SECRET)
    result = TemporalEngine().result(run, timeout=60)
    assert result["note_id"] == str(Note.objects.get().pk)
    assert Note.objects.get().body == SECRET and run.status == FlowRun.Status.COMPLETED

    async def history() -> str:
        handle = temporal.client.get_workflow_handle(run.workflow_id)
        return (await handle.fetch_history()).to_json()

    raw = runner.run(history)
    assert "durable" not in raw and "123.456" not in raw and "joao@example.com" not in raw
    assert "platform-encrypted" in raw or "platform-key-id" in raw


def test_the_request_id_reaches_the_activity_and_its_audit_event(
    temporal: WorkflowEnvironment, user: User, organization: Organization, membership: Membership
) -> None:
    token = request_id_var.set("req-from-http-123")
    try:
        run = start_greet(user, organization)
    finally:
        request_id_var.reset(token)
    TemporalEngine().result(run, timeout=60)
    event = AuditEvent.objects.get(action="action.notes.create")
    assert event.request_id == "req-from-http-123"
    assert event.metadata["channel"] == "flow"


def test_a_refusal_is_not_retried(
    temporal: WorkflowEnvironment, user: User, organization: Organization, membership: Membership
) -> None:
    run = TemporalEngine().start(
        "test.refused",
        {},
        organization=organization,
        actor=user,
    )
    with pytest.raises(WorkflowFailureError) as failure:
        TemporalEngine().result(run, timeout=60)
    assert "invalid" in str(failure.value.cause.cause).lower()

    async def attempts() -> int:
        handle = temporal.client.get_workflow_handle(run.workflow_id)
        events = (await handle.fetch_history()).events
        return sum(1 for e in events if e.event_type == 11)  # ACTIVITY_TASK_SCHEDULED

    assert runner.run(attempts) == 1


def test_timers_signals_and_status_work_with_time_skipping(
    temporal: WorkflowEnvironment, organization: Organization
) -> None:
    engine = TemporalEngine()
    run = engine.start("test.approval", {}, organization=organization)
    assert engine.refresh(run).status == FlowRun.Status.RUNNING

    runner.run(lambda: temporal.sleep(timedelta(days=3, minutes=1)))  # three days in a blink
    engine.signal(run, "approve")
    assert engine.result(run, timeout=60) == "approved"
    assert run.status == FlowRun.Status.COMPLETED


def test_cancelling_a_running_flow(
    temporal: WorkflowEnvironment, organization: Organization
) -> None:
    engine = TemporalEngine()
    run = engine.start("test.approval", {}, organization=organization)
    engine.cancel(run)
    assert run.status == FlowRun.Status.CANCELLED


def test_workflow_code_replays_its_own_history(
    temporal: WorkflowEnvironment, user: User, organization: Organization, membership: Membership
) -> None:
    run = start_greet(user, organization)
    TemporalEngine().result(run, timeout=60)

    async def replay() -> None:
        handle = temporal.client.get_workflow_handle(run.workflow_id)
        history = await handle.fetch_history()
        replayer = Replayer(workflows=[flow_fixtures.Greet], data_converter=build_data_converter())
        await replayer.replay_workflow(history)

    runner.run(replay, timeout=60)


@task
def record_note(title: str) -> str:
    from apps.accounts.models import User as U
    from apps.organizations.models import Organization as O

    Note.objects.create(organization=O.objects.get(), title=title, created_by=U.objects.get())
    return title


def test_django_tasks_run_as_workflows(
    temporal: WorkflowEnvironment, user: User, organization: Organization, membership: Membership
) -> None:
    with override_settings(
        TASKS={"default": {"BACKEND": "apps.flows.task_backend.TemporalTaskBackend"}}
    ):
        from django.tasks import task_backends

        task_backends._settings = {
            "default": {"BACKEND": "apps.flows.task_backend.TemporalTaskBackend"}
        }
        task_backends._connections = type(task_backends._connections)()
        queued = record_note.using().enqueue(title="from a task")
        assert queued.status.value in {"READY", "RUNNING"}
        run = FlowRun.objects.get(pk=queued.id)
        TemporalEngine().result(run, timeout=60)
        fresh = record_note.get_result(queued.id)
        assert fresh.status.value == "SUCCESSFUL" and fresh.return_value == "from a task"
    assert Note.objects.filter(title="from a task").exists()


@pytest.fixture
def dev_server() -> Iterator[WorkflowEnvironment]:
    """The time-skipping server has no Schedules API; the dev server does."""
    env = runner.run(
        lambda: WorkflowEnvironment.start_local(data_converter=build_data_converter()), timeout=240
    )
    yield env
    runner.run(env.shutdown, timeout=60)


def test_schedules_are_created_updated_and_pruned(dev_server: WorkflowEnvironment) -> None:
    from apps.flows.schedules import sync_schedules

    temporal = dev_server

    async def sync(prune: bool) -> dict[str, list[str]]:
        return await sync_schedules(temporal.client, prune=prune)

    first = runner.run(lambda: sync(False))
    assert "job:maintenance.close_idle_runs" in first["created"]
    second = runner.run(lambda: sync(False))
    assert "job:maintenance.close_idle_runs" in second["updated"] and not second["created"]

    async def add_orphan_then_prune() -> list[str]:
        from temporalio.client import Schedule, ScheduleActionStartWorkflow, ScheduleSpec

        await temporal.client.create_schedule(
            "job:gone",
            Schedule(
                action=ScheduleActionStartWorkflow(
                    "platform.job", id="x", task_queue="q", args=[{"name": "x"}]
                ),
                spec=ScheduleSpec(cron_expressions=["0 0 1 1 *"]),
            ),
        )
        return (await sync_schedules(temporal.client, prune=True))["deleted"]

    assert runner.run(add_orphan_then_prune) == ["job:gone"]
    assert json.dumps(first)  # report is plain data
