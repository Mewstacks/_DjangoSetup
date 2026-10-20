"""The data-subject-request flow. Sandbox-safe: orchestration only, the work is in activities.

    execute  ->  done            (access, erasure, blocking... the platform can do these alone)
             ->  needs_review    (correction, opposition...: a person must decide)
                    wait for `review_done`, waking at D-5, D-1, the deadline and daily after
                    to remind the DPO, then `finish`

With Temporal off the same process runs inline (`run_dsar_local`): `execute` once, and the
reminders become the hourly `privacy.dsar_sla` job. The deadline logic is shared.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel
from temporalio import workflow

from apps.flows.sdk import DEFAULT_RETRY, flow
from apps.privacy.timing import next_reminder

STEP_ACTIVITY = "privacy.dsar_step"


class DsarInput(BaseModel):
    request_id: str


class StepCall(BaseModel):
    request_id: str
    step: str
    # The workflow's own clock, so a reminder is decided by the time the workflow lives in and
    # not by the worker's wall clock (they differ in tests and after long waits).
    now: str | None = None


def run_dsar_local(payload: dict[str, Any]) -> dict[str, Any]:
    from apps.privacy.activities import dsar_step_impl

    return dsar_step_impl(str(payload["request_id"]), "execute")


@flow("privacy.dsar", input=DsarInput, local=run_dsar_local)
class DsarWorkflow:
    """Carry out one data subject request within its legal deadline."""

    def __init__(self) -> None:
        self.reviewed = False

    @workflow.signal
    def review_done(self) -> None:
        self.reviewed = True

    async def _step(self, request_id: str, step: str) -> dict[str, Any]:
        result: dict[str, Any] = await workflow.execute_activity(
            STEP_ACTIVITY,
            StepCall(request_id=request_id, step=step, now=workflow.now().isoformat()),
            result_type=dict,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=DEFAULT_RETRY,
        )
        return result

    @workflow.run
    async def run(self, data: DsarInput) -> dict[str, Any]:
        outcome = await self._step(data.request_id, "execute")
        if outcome.get("state") != "needs_review":
            return outcome
        due = datetime.fromisoformat(outcome["due_at"])
        while not self.reviewed:
            wake = next_reminder(workflow.now(), due)
            try:
                await workflow.wait_condition(
                    lambda: self.reviewed, timeout=max(wake - workflow.now(), timedelta(seconds=1))
                )
            except TimeoutError:
                await self._step(data.request_id, "remind")
        return await self._step(data.request_id, "status")
