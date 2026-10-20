"""What a workflow file imports. No Django, no models: it runs inside Temporal's sandbox.

Workflows are orchestration only - ordering, timers, signals, retries. The work itself is done
by *actions* (``call_action``), *jobs* (``call_job``) or custom activities, which run outside
the sandbox with the ORM available::

    from apps.flows.sdk import call_action, flow

    @flow("onboarding.welcome", input=WelcomeInput)
    class Welcome:
        @workflow.run
        async def run(self, data: WelcomeInput) -> dict:
            await call_action("notes.create", organization_id=data.org, actor_id=data.user,
                              payload={"title": "Welcome"})
            await workflow.sleep(timedelta(days=3))
            ...
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field
from temporalio import workflow
from temporalio.common import RetryPolicy

from apps.flows.declare import flow, job, local_flow

ACTION_ACTIVITY = "platform.run_action"
JOB_ACTIVITY = "platform.run_job"
TASK_ACTIVITY = "platform.run_task"

# Errors that retrying cannot fix: the activity maps every DomainError to one of these types.
NON_RETRYABLE = ["Forbidden", "Invalid", "NotFound", "Conflict", "Unauthenticated"]
DEFAULT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=5,
    non_retryable_error_types=NON_RETRYABLE,
)


class ActionCall(BaseModel):
    name: str
    organization_id: str
    actor_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class JobCall(BaseModel):
    name: str
    timeout_seconds: int = 600


class TaskCall(BaseModel):
    path: str
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = 3


async def call_action(
    name: str,
    *,
    organization_id: str,
    actor_id: str,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    timeout: timedelta = timedelta(minutes=5),
    retry: RetryPolicy = DEFAULT_RETRY,
) -> dict[str, Any]:
    """Run an action as ``actor_id`` in ``organization_id`` (membership is re-checked live)."""
    key = idempotency_key or f"flow:{workflow.info().workflow_id}:{name}:{workflow.uuid4()}"
    result: dict[str, Any] = await workflow.execute_activity(
        ACTION_ACTIVITY,
        ActionCall(
            name=name,
            organization_id=organization_id,
            actor_id=actor_id,
            payload=payload or {},
            idempotency_key=key,
        ),
        result_type=dict,
        start_to_close_timeout=timeout,
        retry_policy=retry,
    )
    return result


async def call_job(
    name: str, *, timeout: timedelta = timedelta(minutes=10), retry: RetryPolicy = DEFAULT_RETRY
) -> dict[str, Any]:
    result: dict[str, Any] = await workflow.execute_activity(
        JOB_ACTIVITY,
        JobCall(name=name, timeout_seconds=int(timeout.total_seconds())),
        result_type=dict,
        start_to_close_timeout=timeout,
        retry_policy=retry,
    )
    return result


__all__ = [
    "ACTION_ACTIVITY",
    "DEFAULT_RETRY",
    "JOB_ACTIVITY",
    "TASK_ACTIVITY",
    "ActionCall",
    "JobCall",
    "TaskCall",
    "call_action",
    "call_job",
    "flow",
    "job",
    "local_flow",
]
