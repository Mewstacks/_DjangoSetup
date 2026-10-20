"""Business rules for notes: one implementation, called by REST viewsets and by actions."""

from __future__ import annotations

from django.utils import timezone

from apps.actions.context import ActionContext
from apps.common.exceptions import Conflict
from apps.examples.models import Note


def create_note(ctx: ActionContext, *, title: str, body: str = "") -> Note:
    note = Note.objects.create(
        organization=ctx.organization, title=title.strip(), body=body, created_by=ctx.user
    )
    ctx.set_target(note)
    return note


def update_note(
    ctx: ActionContext, note: Note, *, title: str | None = None, body: str | None = None
) -> Note:
    if note.archived_at is not None:
        raise Conflict("An archived note cannot be edited.", code="note_archived")
    if title is not None:
        note.title = title.strip()
    if body is not None:
        note.body = body
    note.save(update_fields=["title", "body", "updated_at"])
    ctx.set_target(note)
    return note


def archive_note(ctx: ActionContext, note: Note) -> Note:
    if note.archived_at is None:
        note.archived_at = timezone.now()
        note.save(update_fields=["archived_at", "updated_at"])
    ctx.set_target(note)
    return note
