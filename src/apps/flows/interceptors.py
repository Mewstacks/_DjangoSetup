"""Carry request/organization/actor/channel from the caller through workflows into activities.

One header, ``x-platform-context``, rides on every client call and every activity a workflow
starts. Activities rebuild the logging context from it, so a log line written in a worker three
days later still carries the ``request_id`` of the HTTP request that started the flow - and the
organization and actor it belongs to.

The same interceptor makes each activity safe for Django: a worker thread has no request cycle
to open and close database connections, so ``close_old_connections()`` brackets every call.

Nothing Django-specific is imported at module level, because the workflow-side classes are
instantiated inside Temporal's sandbox.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any

import temporalio.activity
import temporalio.api.common.v1
import temporalio.client
import temporalio.converter
import temporalio.worker
import temporalio.workflow

from apps.common.context import LOG_CONTEXT_VARS

HEADER = "x-platform-context"
KEYS = ("request_id", "organization_id", "actor_id", "channel")


def _headers_with(
    existing: Mapping[str, temporalio.api.common.v1.Payload],
    context: dict[str, str],
    converter: temporalio.converter.PayloadConverter,
) -> Mapping[str, temporalio.api.common.v1.Payload]:
    if not context:
        return existing
    return {**existing, HEADER: converter.to_payload(context)}


def _current_context() -> dict[str, str]:
    context: dict[str, str] = {}
    for key in KEYS:
        value = LOG_CONTEXT_VARS[key].get()
        if value:
            context[key] = value
    return context


@contextmanager
def _bound(context: dict[str, str]) -> Any:
    tokens = [(LOG_CONTEXT_VARS[k], LOG_CONTEXT_VARS[k].set(v)) for k, v in context.items()]
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


def _read(
    headers: Mapping[str, temporalio.api.common.v1.Payload],
    converter: temporalio.converter.PayloadConverter,
) -> dict[str, str]:
    payload = headers.get(HEADER)
    if payload is None:
        return {}
    value = converter.from_payload(payload, dict)
    return {k: str(v) for k, v in value.items() if k in KEYS}


class PlatformInterceptor(temporalio.client.Interceptor, temporalio.worker.Interceptor):
    def __init__(self, payload_converter: temporalio.converter.PayloadConverter | None = None):
        self._converter = payload_converter or temporalio.converter.default().payload_converter

    def intercept_client(
        self, next: temporalio.client.OutboundInterceptor
    ) -> temporalio.client.OutboundInterceptor:
        return _ClientOutbound(next, self._converter)

    def intercept_activity(
        self, next: temporalio.worker.ActivityInboundInterceptor
    ) -> temporalio.worker.ActivityInboundInterceptor:
        return _ActivityInbound(next)

    def workflow_interceptor_class(
        self, input: temporalio.worker.WorkflowInterceptorClassInput
    ) -> type[_WorkflowInbound]:
        return _WorkflowInbound


class _ClientOutbound(temporalio.client.OutboundInterceptor):
    def __init__(self, next: temporalio.client.OutboundInterceptor, converter: Any) -> None:
        super().__init__(next)
        self._converter = converter

    async def start_workflow(self, input: temporalio.client.StartWorkflowInput) -> Any:
        input.headers = _headers_with(input.headers, _current_context(), self._converter)
        return await super().start_workflow(input)

    async def signal_workflow(self, input: temporalio.client.SignalWorkflowInput) -> None:
        input.headers = _headers_with(input.headers, _current_context(), self._converter)
        await super().signal_workflow(input)


class _ActivityInbound(temporalio.worker.ActivityInboundInterceptor):
    async def execute_activity(self, input: temporalio.worker.ExecuteActivityInput) -> Any:
        from django.db import close_old_connections

        context = _read(input.headers, temporalio.activity.payload_converter())
        info = temporalio.activity.info()
        context["workflow_id"] = info.workflow_id or ""
        context["activity"] = info.activity_type
        with _bound({k: v for k, v in context.items() if v}):
            # Sync activities run in a thread pool; this thread has no request cycle, so
            # stale or dead connections would otherwise be reused until the DB closes them.
            close_old_connections()
            try:
                return await self.next.execute_activity(input)
            finally:
                close_old_connections()


class _WorkflowInbound(temporalio.worker.WorkflowInboundInterceptor):
    """Remembers the incoming header so every activity the workflow starts carries it."""

    def init(self, outbound: temporalio.worker.WorkflowOutboundInterceptor) -> None:
        self._holder: dict[str, Any] = {}
        self.next.init(_WorkflowOutbound(outbound, self._holder))

    async def execute_workflow(self, input: temporalio.worker.ExecuteWorkflowInput) -> Any:
        payload = input.headers.get(HEADER)
        if payload is not None:
            self._holder["payload"] = payload
        return await self.next.execute_workflow(input)

    async def handle_signal(self, input: temporalio.worker.HandleSignalInput) -> None:
        payload = input.headers.get(HEADER)
        if payload is not None:
            self._holder["payload"] = payload
        await self.next.handle_signal(input)


class _WorkflowOutbound(temporalio.worker.WorkflowOutboundInterceptor):
    def __init__(
        self, next: temporalio.worker.WorkflowOutboundInterceptor, holder: dict[str, Any]
    ) -> None:
        super().__init__(next)
        self._holder = holder

    def _with_context(self, input: Any) -> None:
        payload = self._holder.get("payload")
        if payload is not None:
            input.headers = {**input.headers, HEADER: payload}

    def start_activity(self, input: temporalio.worker.StartActivityInput) -> Any:
        self._with_context(input)
        return super().start_activity(input)

    def start_local_activity(self, input: temporalio.worker.StartLocalActivityInput) -> Any:
        self._with_context(input)
        return super().start_local_activity(input)

    async def start_child_workflow(self, input: temporalio.worker.StartChildWorkflowInput) -> Any:
        self._with_context(input)
        return await super().start_child_workflow(input)
