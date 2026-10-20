"""Temporal Schedules for jobs that declare a cron expression.

``sync_schedules`` is idempotent: it creates what is missing, updates what changed and, with
``prune=True``, deletes schedules this project created (ids ``job:<name>``) whose job no longer
exists. Overlap policy is SKIP - a slow run is never stacked behind itself - and a missed run
is caught up only within an hour.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
    ScheduleUpdateInput,
)

from apps.flows.declare import JOBS, JobSpec
from apps.flows.sdk import JobCall

PREFIX = "job:"


def schedule_for(spec: JobSpec) -> Schedule:
    assert spec.schedule
    return Schedule(
        action=ScheduleActionStartWorkflow(
            "platform.job",
            JobCall(name=spec.name, timeout_seconds=int(spec.timeout.total_seconds())),
            id=f"{PREFIX}{spec.name}",
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        ),
        spec=ScheduleSpec(cron_expressions=[spec.schedule]),
        policy=SchedulePolicy(
            overlap=ScheduleOverlapPolicy.SKIP, catchup_window=timedelta(hours=1)
        ),
        state=ScheduleState(note=spec.description[:200] or None),
    )


async def sync_schedules(client: Client, *, prune: bool = False) -> dict[str, list[str]]:
    report: dict[str, list[str]] = {"created": [], "updated": [], "deleted": []}
    wanted = {f"{PREFIX}{s.name}": s for s in JOBS.values() if s.schedule}
    for schedule_id, spec in wanted.items():
        desired = schedule_for(spec)
        try:
            await client.create_schedule(schedule_id, desired)
            report["created"].append(schedule_id)
        except ScheduleAlreadyRunningError:
            handle = client.get_schedule_handle(schedule_id)

            async def replace(
                update: ScheduleUpdateInput, desired: Schedule = desired
            ) -> ScheduleUpdate:
                # Keep a paused schedule paused: pausing is an operator's decision.
                desired.state.paused = update.description.schedule.state.paused
                return ScheduleUpdate(schedule=desired)

            await handle.update(replace)
            report["updated"].append(schedule_id)
    if prune:
        async for listed in await client.list_schedules():
            if listed.id.startswith(PREFIX) and listed.id not in wanted:
                await client.get_schedule_handle(listed.id).delete()
                report["deleted"].append(listed.id)
    return report
