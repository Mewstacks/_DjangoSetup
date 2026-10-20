"""Business rules for notes: one implementation, called by REST viewsets and by actions."""

from __future__ import annotations

from django.utils import timezone

from apps.actions.context import ActionContext
from apps.actions.journal import snapshot
from apps.common.exceptions import Conflict
from apps.examples.models import Note
from apps.webhooks.services import emit

SNAPSHOT_FIELDS = ("title", "body", "archived_at")


def create_note(ctx: ActionContext, *, title: str, body: str = "") -> Note:
    note = Note.objects.create(
        organization=ctx.organization, title=title.strip(), body=body, created_by=ctx.user
    )
    ctx.set_target(note)
    ctx.record_change("create", note, after=snapshot(note, SNAPSHOT_FIELDS), label=note.title)
    emit("note.created", ctx.organization, {"note_id": str(note.pk)})
    return note


def update_note(
    ctx: ActionContext, note: Note, *, title: str | None = None, body: str | None = None
) -> Note:
    if note.archived_at is not None:
        raise Conflict("An archived note cannot be edited.", code="note_archived")
    before = snapshot(note, SNAPSHOT_FIELDS)
    if title is not None:
        note.title = title.strip()
    if body is not None:
        note.body = body
    note.save(update_fields=["title", "body", "updated_at"])
    ctx.set_target(note)
    ctx.record_change(
        "update", note, before=before, after=snapshot(note, SNAPSHOT_FIELDS), label=note.title
    )
    return note


def archive_note(ctx: ActionContext, note: Note) -> Note:
    if note.archived_at is None:
        before = snapshot(note, SNAPSHOT_FIELDS)
        note.archived_at = timezone.now()
        note.save(update_fields=["archived_at", "updated_at"])
        ctx.record_change(
            "archive", note, before=before, after=snapshot(note, SNAPSHOT_FIELDS), label=note.title
        )
        emit("note.archived", ctx.organization, {"note_id": str(note.pk)})
    ctx.set_target(note)
    return note
