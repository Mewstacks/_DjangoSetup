"""Actions every deployment gets: the change journal, undo and the agent run report."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from apps.actions.context import ActionContext
from apps.actions.journal import undo_entry
from apps.actions.models import ActionJournal, AgentRun
from apps.actions.registry import action
from apps.common.exceptions import NotFound


class ChangeOut(BaseModel):
    id: uuid.UUID
    action: str
    op: str
    target_type: str
    target_id: str
    label: str
    status: str
    created_at: datetime


class ChangeList(BaseModel):
    items: list[ChangeOut]


class ListChanges(BaseModel):
    limit: int = Field(20, ge=1, le=50)
    only_applied: bool = True


class ChangeRef(BaseModel):
    id: uuid.UUID


class RunReport(BaseModel):
    summary: str = Field("", max_length=4000)
    model: str = Field("", max_length=80)
    input_tokens: int | None = Field(None, ge=0)
    output_tokens: int | None = Field(None, ge=0)


class RunOut(BaseModel):
    id: uuid.UUID
    tool_calls: int
    duration_ms: int


@action("actions.changes")
def list_changes(ctx: ActionContext, data: ListChanges) -> ChangeList:
    """List the caller's recent changes, newest first, with ids that `actions.undo` accepts."""
    queryset = ctx.scoped(ActionJournal).filter(user=ctx.user)
    if data.only_applied:
        queryset = queryset.filter(status=ActionJournal.Status.APPLIED)
    return ChangeList(
        items=[
            ChangeOut(
                id=e.id,
                action=e.action,
                op=e.op,
                target_type=e.target_type,
                target_id=e.target_id,
                label=e.label,
                status=e.status,
                created_at=e.created_at,
            )
            for e in queryset[: data.limit]
        ]
    )


@action(
    "actions.undo",
    write=True,
    idempotent=True,
    undoable="undoing is itself the way back; to redo, run the original action again",
)
def undo(ctx: ActionContext, data: ChangeRef) -> ChangeOut:
    """Take back one of your own changes. Refuses if the record was edited after it."""
    e = undo_entry(ctx, data.id)
    return ChangeOut(
        id=e.id,
        action=e.action,
        op=e.op,
        target_type=e.target_type,
        target_id=e.target_id,
        label=e.label,
        status=e.status,
        created_at=e.created_at,
    )


@action(
    "agent.report",
    write=True,
    scope="actions:write",
    channels={"mcp"},
    undoable="a time report about the agent's own work; no business data changes",
)
def report_run(ctx: ActionContext, data: RunReport) -> RunOut:
    """Attach a summary and your model name to the current working session (optional)."""
    run = (
        ctx.scoped(AgentRun)
        .select_for_update()
        .filter(credential_id=ctx.credential_id or "", ended_at=None)
        .order_by("-started_at")
        .first()
    )
    if run is None:
        raise NotFound("No open session for this credential.")
    run.summary = data.summary
    run.reported_model = data.model
    run.reported_input_tokens = data.input_tokens
    run.reported_output_tokens = data.output_tokens
    run.save()
    return RunOut(id=run.id, tool_calls=run.tool_calls, duration_ms=run.duration_ms)
