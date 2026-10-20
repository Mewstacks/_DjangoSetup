"""Run ledger, change journal and undo.

An agent acts quickly and sometimes wrongly; the journal is the safety net that makes that
acceptable. A write that wants to be undoable declares what it changed with
``ctx.record_change`` - a snapshot before and after - and registers a handler that knows how
to reverse that kind of change. Undo refuses when the record was edited by somebody else in
the meantime (the snapshot digest no longer matches), instead of overwriting their work.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import models
from django.db.models import Model
from django.utils import timezone

from apps.actions.context import ActionContext
from apps.actions.models import ActionJournal, AgentRun
from apps.common.exceptions import Conflict, Forbidden, NotFound

RUN_IDLE_GAP = timedelta(minutes=15)


def snapshot(instance: Model, fields: tuple[str, ...]) -> dict[str, Any]:
    """JSON-safe state of ``fields``. Related objects are stored by primary key."""
    state: dict[str, Any] = {}
    for name in fields:
        value = getattr(instance, name)
        if isinstance(value, models.Model):
            value = str(value.pk)
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        elif value is not None and not isinstance(value, str | int | float | bool | list | dict):
            value = str(value)
        state[name] = value
    return state


def digest(state: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


# --- runs ---------------------------------------------------------------------------------


def attach_run(ctx: ActionContext) -> AgentRun | None:
    """Create or extend the open run of this credential.

    MCP is stateless, so a model will not echo a run id; the credential plus an idle gap is the
    only grouping available. The span ends at the *last* call, so idle time is never counted.
    """
    if ctx.channel != "mcp" or not ctx.credential_id:
        return None
    now = timezone.now()
    run = (
        AgentRun.objects.select_for_update()
        .filter(organization=ctx.organization, credential_id=ctx.credential_id, ended_at=None)
        .order_by("-started_at")
        .first()
    )
    if run is not None and now - run.last_call_at > RUN_IDLE_GAP:
        run.ended_at = run.last_call_at
        run.save(update_fields=["ended_at", "updated_at"])
        run = None
    if run is None:
        run = AgentRun.objects.create(
            organization=ctx.organization,
            credential_id=ctx.credential_id,
            user=ctx.user,
            started_at=now,
            last_call_at=now,
        )
    run.last_call_at = now
    run.tool_calls += 1
    run.duration_ms = int((now - run.started_at).total_seconds() * 1000)
    run.save(update_fields=["last_call_at", "tool_calls", "duration_ms", "updated_at"])
    return run


def close_idle_runs() -> int:
    """Close runs idle past the gap. Run from a schedule; returns how many were closed."""
    cutoff = timezone.now() - RUN_IDLE_GAP
    closed = 0
    for run in AgentRun.objects.filter(ended_at=None, last_call_at__lt=cutoff):
        run.ended_at = run.last_call_at
        run.save(update_fields=["ended_at", "updated_at"])
        closed += 1
    return closed


def purge_journal() -> int:
    """Delete journal rows past retention: they hold snapshots of business data."""
    days = int(getattr(settings, "ACTIONS_JOURNAL_RETENTION_DAYS", 30))
    deleted, _ = ActionJournal.objects.filter(
        created_at__lt=timezone.now() - timedelta(days=days)
    ).delete()
    return int(deleted)


# --- journal ------------------------------------------------------------------------------


def persist_changes(ctx: ActionContext, action: str, run: AgentRun | None) -> None:
    channels = set(getattr(settings, "ACTIONS_JOURNAL_CHANNELS", ("mcp",)))
    if ctx.channel not in channels:
        ctx.changes.clear()
        return
    for change in ctx.changes:
        ActionJournal.objects.create(
            organization=ctx.organization,
            run=run,
            credential_id=ctx.credential_id or "",
            user=ctx.user,
            action=action,
            **change,
        )
    ctx.changes.clear()


# --- undo ---------------------------------------------------------------------------------

UndoHandler = Callable[[ActionContext, ActionJournal, Model], None]
_HANDLERS: dict[tuple[str, str], tuple[type[Model], UndoHandler]] = {}


def undo_handler(model: type[Model], op: str) -> Callable[[UndoHandler], UndoHandler]:
    """Register how to reverse ``op`` on ``model``; the handler gets the live row."""

    def decorator(fn: UndoHandler) -> UndoHandler:
        _HANDLERS[(model._meta.label_lower, op)] = (model, fn)
        return fn

    return decorator


def expect_unchanged(entry: ActionJournal, current: dict[str, Any]) -> None:
    """Refuse to undo over somebody else's later edit."""
    if digest(current) != digest(entry.after):
        raise Conflict(
            "The record changed after this action; undo would overwrite that change.",
            code="changed_since",
        )


def undo_entry(ctx: ActionContext, journal_id: Any) -> ActionJournal:
    from apps.actions.registry import get_action

    entry = (
        ActionJournal.objects.select_for_update()
        .filter(organization=ctx.organization, user=ctx.user, pk=journal_id)
        .first()
    )
    if entry is None:
        raise NotFound("No such change.")
    if entry.status != ActionJournal.Status.APPLIED:
        raise Conflict("This change was already undone.", code="already_undone")
    original = get_action(entry.action)
    if original is not None and not ctx.has_scope(original.scope):
        raise Forbidden(f"Undoing this needs the scope {original.scope}.", code="missing_scope")
    handler = _HANDLERS.get((entry.target_type, entry.op))
    if handler is None:
        raise Conflict("This kind of change cannot be undone.", code="not_undoable")
    model, fn = handler
    row = model._default_manager.filter(pk=entry.target_id).first()
    if row is None:
        raise NotFound("The record no longer exists.")
    fn(ctx, entry, row)
    entry.status = ActionJournal.Status.UNDONE
    entry.undone_at = timezone.now()
    entry.save(update_fields=["status", "undone_at", "updated_at"])
    return entry
