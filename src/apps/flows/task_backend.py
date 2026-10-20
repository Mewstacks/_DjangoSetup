"""``django.tasks`` backend that runs tasks as Temporal workflows.

    from django.tasks import task

    @task(queue_name="default")
    def send_report(report_id: str) -> None: ...

    send_report.enqueue(report_id="...")      # a workflow `platform.task` is started

This is deliberately narrow. ``django.tasks`` has no workflow semantics, so the backend maps
only what it can honestly keep: enqueue (immediately, or on commit when inside a
transaction), ``run_after`` (as a workflow start delay), results (read back from Temporal)
and retries (the workflow's retry policy: 3 attempts with exponential backoff). Arguments
must be JSON, as Django requires; ``takes_context`` and priorities are not supported. When
Temporal is off, ``TASKS`` points at Django's ``ImmediateBackend`` instead.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.tasks.backends.base import BaseTaskBackend
from django.tasks.base import Task, TaskError, TaskResult, TaskResultStatus
from django.tasks.exceptions import InvalidTask, TaskResultDoesNotExist
from django.utils import timezone
from django.utils.module_loading import import_string

from apps.flows.declare import FLOWS
from apps.flows.engine import TemporalEngine, _new_run
from apps.flows.models import FlowRun
from apps.flows.sdk import TaskCall

_STATUS = {
    FlowRun.Status.PENDING: TaskResultStatus.READY,
    FlowRun.Status.RUNNING: TaskResultStatus.RUNNING,
    FlowRun.Status.COMPLETED: TaskResultStatus.SUCCESSFUL,
    FlowRun.Status.FAILED: TaskResultStatus.FAILED,
    FlowRun.Status.CANCELLED: TaskResultStatus.FAILED,
}


class TemporalTaskBackend(BaseTaskBackend):
    supports_defer = True
    supports_get_result = True
    supports_async_task = False
    supports_priority = False

    def validate_task(self, task: Task[Any, Any]) -> None:
        super().validate_task(task)
        if task.takes_context:
            raise InvalidTask("Temporal-backed tasks do not support takes_context.")

    def enqueue(
        self, task: Task[Any, Any], args: list[Any], kwargs: dict[str, Any]
    ) -> TaskResult[Any, Any]:
        self.validate_task(task)
        spec = FLOWS["platform.task"]
        call = TaskCall(path=task.module_path, args=list(args), kwargs=dict(kwargs))
        data = call.model_dump(mode="json")
        run = _new_run(spec, "temporal", data, None, None, f"task:{task.module_path}")
        run.workflow_id = f"task:{run.pk}"
        run.save(update_fields=["workflow_id", "updated_at"])
        delay: timedelta | None = None
        if task.run_after is not None:
            delay = max(task.run_after - timezone.now(), timedelta(0))

        def launch() -> None:
            TemporalEngine().launch(run, spec, data, delay)

        # Inside a transaction the workflow must not start before the rows the task refers
        # to are committed, or it would race the very data it needs.
        if transaction.get_connection().in_atomic_block:
            transaction.on_commit(launch)
        else:
            launch()
        return self._result(task, run)

    def _result(self, task: Task[Any, Any], run: FlowRun) -> TaskResult[Any, Any]:
        call = json.loads(run.input_json) if run.input_json else {}
        result: TaskResult[Any, Any] = TaskResult(
            task=task,
            id=str(run.pk),
            status=_STATUS[FlowRun.Status(run.status)],
            enqueued_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            last_attempted_at=run.started_at,
            args=call.get("args", []),
            kwargs=call.get("kwargs", {}),
            backend=self.alias,
            errors=(
                [TaskError(exception_class_path="builtins.RuntimeError", traceback=run.error)]
                if run.error
                else []
            ),
            worker_ids=[],
        )
        if run.status == FlowRun.Status.COMPLETED and run.result_json:
            object.__setattr__(result, "_return_value", json.loads(run.result_json))
        return result

    def get_result(self, result_id: str) -> TaskResult[Any, Any]:
        run = FlowRun.objects.filter(pk=result_id, flow="platform.task").first()
        if run is None:
            raise TaskResultDoesNotExist(result_id)
        TemporalEngine().refresh(run)
        call = json.loads(run.input_json)
        task = import_string(call["path"])
        return self._result(task, run)
