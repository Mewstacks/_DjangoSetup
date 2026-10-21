"""Flows as actions: start, follow and cancel runs from REST, MCP, the CLI or another flow."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from apps.actions.context import ActionContext
from apps.actions.registry import action
from apps.common.exceptions import Forbidden, Invalid, NotFound
from apps.flows.declare import FLOWS
from apps.flows.engine import IDENTITY_KEYS, capabilities, get_engine
from apps.flows.models import FlowRun


class FlowInfo(BaseModel):
    name: str
    description: str
    portable: bool
    startable: bool


class FlowCatalog(BaseModel):
    engine: str
    flows: list[FlowInfo]
    capabilities: list[dict[str, Any]]


class RunRef(BaseModel):
    id: uuid.UUID


class StartFlow(BaseModel):
    flow: str = Field(min_length=3, max_length=120)
    input: dict[str, Any] = Field(default_factory=dict)


class SignalFlow(BaseModel):
    id: uuid.UUID
    name: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any] | None = None


class RunOut(BaseModel):
    id: uuid.UUID
    flow: str
    engine: str
    status: str
    error: str
    started_at: datetime | None
    finished_at: datetime | None
    result: Any | None = None

    @classmethod
    def of(cls, run: FlowRun, result: Any | None = None) -> RunOut:
        return cls(
            id=run.id,
            flow=run.flow,
            engine=run.engine,
            status=run.status,
            error=run.error,
            started_at=run.started_at,
            finished_at=run.finished_at,
            result=result,
        )


class RunList(BaseModel):
    items: list[RunOut]


class ListRuns(BaseModel):
    limit: int = Field(20, ge=1, le=50)
    flow: str | None = None


@action("flows.catalog", scope="flows:read", channels={"api", "mcp", "cli"})
def catalog(ctx: ActionContext) -> FlowCatalog:
    """Which engine runs flows here, which flows exist, and what each engine can and cannot do."""
    return FlowCatalog(
        engine=get_engine().name,
        flows=[
            FlowInfo(
                name=s.name,
                description=s.description,
                portable=s.portable,
                startable=s.startable,
            )
            for s in sorted(FLOWS.values(), key=lambda s: s.name)
        ],
        capabilities=capabilities(),
    )


@action("flows.runs", scope="flows:read")
def list_runs(ctx: ActionContext, data: ListRuns) -> RunList:
    """List recent flow runs of this organization."""
    queryset = ctx.scoped_nullable(FlowRun)
    if data.flow:
        queryset = queryset.filter(flow=data.flow)
    return RunList(items=[RunOut.of(r) for r in queryset[: data.limit]])


@action("flows.status", scope="flows:read")
def status(ctx: ActionContext, data: RunRef) -> RunOut:
    """Current status of one run (refreshed from Temporal when that engine ran it)."""
    run = _run(ctx, data.id)
    get_engine_for(run).refresh(run)
    return RunOut.of(run)


@action(
    "flows.start",
    write=True,
    undoable="a started run is stopped with flows.cancel; what it already did is its own",
)
def start(ctx: ActionContext, data: StartFlow) -> RunOut:
    """Start one of the flows marked startable. Safe to call with an Idempotency-Key."""
    spec = FLOWS.get(data.flow)
    if spec is None or not spec.startable:
        raise NotFound("Unknown flow.")
    reserved = sorted(set(IDENTITY_KEYS) & set(data.input))
    if reserved:
        # Identity is the caller's, never an input: see engine._validated.
        raise Invalid(f"{', '.join(reserved)} cannot be set; the flow runs as you.")
    if not ctx.has_scope(spec.scope):
        raise Forbidden(f"This credential lacks the scope {spec.scope}.", code="missing_scope")
    run = get_engine().start(data.flow, data.input, organization=ctx.organization, actor=ctx.user)
    ctx.set_target(run)
    return RunOut.of(run)


@action("flows.signal", write=True, undoable="a delivered signal cannot be recalled")
def signal(ctx: ActionContext, data: SignalFlow) -> RunOut:
    """Send a signal to a running flow (Temporal engine only)."""
    run = _run(ctx, data.id)
    get_engine_for(run).signal(run, data.name, data.payload)
    ctx.set_target(run)
    return RunOut.of(run)


@action(
    "flows.cancel",
    write=True,
    destructive=True,
    undoable="a cancelled run cannot be resumed; start a new one",
)
def cancel(ctx: ActionContext, data: RunRef) -> RunOut:
    """Cancel a running flow (Temporal engine only)."""
    run = _run(ctx, data.id)
    get_engine_for(run).cancel(run)
    ctx.set_target(run)
    return RunOut.of(run)


def _run(ctx: ActionContext, run_id: uuid.UUID) -> FlowRun:
    run = ctx.scoped_nullable(FlowRun).filter(pk=run_id).first()
    if run is None:
        raise NotFound("Run not found.")
    assert isinstance(run, FlowRun)
    return run


def get_engine_for(run: FlowRun) -> Any:
    from apps.flows.engine import _local, _temporal

    return _temporal if run.engine == "temporal" else _local
