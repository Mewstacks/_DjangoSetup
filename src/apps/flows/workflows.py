"""Generic workflows: run one job, run one Django task. Sandbox-safe (no Django imports)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

from apps.flows.sdk import (
    DEFAULT_RETRY,
    JOB_ACTIVITY,
    NON_RETRYABLE,
    TASK_ACTIVITY,
    JobCall,
    TaskCall,
    flow,
)


def _local_job(payload: dict[str, Any]) -> dict[str, Any]:
    from apps.flows.jobs_runtime import execute_job

    return execute_job(str(payload["name"]))


def _local_task(payload: dict[str, Any]) -> Any:
    from django.utils.module_loading import import_string

    return import_string(payload["path"]).call(
        *payload.get("args", []), **payload.get("kwargs", {})
    )


@flow("platform.job", input=JobCall, local=_local_job)
class JobWorkflow:
    """Run a registered job once (scheduled jobs start here)."""

    @workflow.run
    async def run(self, call: JobCall) -> dict[str, Any]:
        result: dict[str, Any] = await workflow.execute_activity(
            JOB_ACTIVITY,
            call,
            result_type=dict,
            start_to_close_timeout=timedelta(seconds=call.timeout_seconds),
            retry_policy=DEFAULT_RETRY,
        )
        return result


@flow("platform.task", input=TaskCall, local=_local_task)
class TaskWorkflow:
    """Run a `django.tasks` task with Temporal's retries."""

    @workflow.run
    async def run(self, call: TaskCall) -> Any:
        return await workflow.execute_activity(
            TASK_ACTIVITY,
            call,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(minutes=5),
                maximum_attempts=max(1, call.max_attempts),
                non_retryable_error_types=NON_RETRYABLE,
            ),
        )
