"""The activities every worker runs: they bridge Temporal to actions, jobs and Django tasks.

All three are *sync* functions on purpose. They run in the worker's thread pool, so the ORM
works exactly as in a request thread; ``PlatformInterceptor`` brackets each call with
``close_old_connections()``. Async activities would force ``sync_to_async`` around every query
for no benefit (see docs/adr/temporal-sync-activities).
"""

from __future__ import annotations

from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from apps.common.exceptions import DomainError
from apps.flows.sdk import (
    ACTION_ACTIVITY,
    JOB_ACTIVITY,
    TASK_ACTIVITY,
    ActionCall,
    JobCall,
    TaskCall,
)


def _non_retryable(error: DomainError) -> ApplicationError:
    """A refusal is the answer, not a glitch: do not let Temporal retry it five times."""
    return ApplicationError(
        f"{error.code}: {error.detail}", type=type(error).__name__, non_retryable=True
    )


@activity.defn(name=ACTION_ACTIVITY)
def run_action(call: ActionCall) -> dict[str, Any]:
    from apps.accounts.models import User
    from apps.actions.context import build_context
    from apps.actions.runtime import invoke
    from apps.common.context import request_id_var
    from apps.organizations.models import Organization

    try:
        user = User.objects.get(pk=call.actor_id)
        organization = Organization.objects.get(pk=call.organization_id)
        ctx = build_context(
            user=user,
            organization=organization,
            channel="flow",
            request_id=request_id_var.get(),
        )
        output, _ = invoke(call.name, ctx, call.payload, idempotency_key=call.idempotency_key)
    except DomainError as error:
        raise _non_retryable(error) from error
    except (User.DoesNotExist, Organization.DoesNotExist) as error:
        raise ApplicationError(
            "Actor or organization no longer exists.", non_retryable=True
        ) from error
    return output


@activity.defn(name=JOB_ACTIVITY)
def run_job(call: JobCall) -> dict[str, Any]:
    from apps.flows.jobs_runtime import execute_job

    return execute_job(call.name)


@activity.defn(name=TASK_ACTIVITY)
def run_task(call: TaskCall) -> Any:
    from django.conf import settings
    from django.tasks import Task
    from django.utils.module_loading import import_string

    if not call.path.startswith(tuple(settings.FLOWS_TASK_MODULE_PREFIXES)):
        raise ApplicationError("That task path is not allowed.", non_retryable=True)
    task = import_string(call.path)
    if not isinstance(task, Task):
        # A dotted path is data; only something declared with @task may be called through it.
        raise ApplicationError("That path is not a task.", non_retryable=True)
    return task.call(*call.args, **call.kwargs)
