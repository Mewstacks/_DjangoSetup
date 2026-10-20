"""Notes as actions: each function below is a REST endpoint, an MCP tool, a Temporal activity
and a CLI command at once. This file is the template for adding your own."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from apps.actions.context import ActionContext
from apps.actions.registry import action
from apps.examples import services, undo  # noqa: F401  (registers the undo handlers)
from apps.examples.models import Note


class NoteOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    archived: bool
    created_at: datetime

    @classmethod
    def of(cls, note: Note) -> NoteOut:
        return cls(
            id=note.id,
            title=note.title,
            body=note.body,
            archived=note.archived_at is not None,
            created_at=note.created_at,
        )


class NoteList(BaseModel):
    total: int
    returned: int
    next_offset: int | None
    items: list[NoteOut]


class ListNotes(BaseModel):
    limit: int = Field(20, ge=1, le=50)
    offset: int = Field(0, ge=0)
    include_archived: bool = False


class NoteRef(BaseModel):
    id: uuid.UUID


class CreateNote(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field("", max_length=20_000)


class UpdateNote(BaseModel):
    id: uuid.UUID
    title: str | None = Field(None, min_length=1, max_length=200)
    body: str | None = Field(None, max_length=20_000)


@action("notes.list")
def list_notes(ctx: ActionContext, data: ListNotes) -> NoteList:
    """List the organization's notes, newest first."""
    queryset = ctx.scoped(Note)
    if not data.include_archived:
        queryset = queryset.filter(archived_at__isnull=True)
    total = queryset.count()
    page = list(queryset[data.offset : data.offset + data.limit])
    next_offset = data.offset + len(page) if data.offset + len(page) < total else None
    return NoteList(
        total=total,
        returned=len(page),
        next_offset=next_offset,
        items=[NoteOut.of(n) for n in page],
    )


@action("notes.get")
def get_note(ctx: ActionContext, data: NoteRef) -> NoteOut:
    """Read one note by id."""
    return NoteOut.of(ctx.get(Note, data.id))


@action("notes.create", write=True)
def create_note(ctx: ActionContext, data: CreateNote) -> NoteOut:
    """Create a note. Send an Idempotency-Key to make retries safe."""
    return NoteOut.of(services.create_note(ctx, title=data.title, body=data.body))


@action("notes.update", write=True, idempotent=True)
def update_note(ctx: ActionContext, data: UpdateNote) -> NoteOut:
    """Change a note's title or body. Archived notes cannot be edited."""
    note = ctx.get(Note, data.id)
    return NoteOut.of(services.update_note(ctx, note, title=data.title, body=data.body))


@action("notes.archive", write=True, idempotent=True, destructive=True)
def archive_note(ctx: ActionContext, data: NoteRef) -> NoteOut:
    """Archive a note. Archived notes are hidden from the default list and read-only."""
    return NoteOut.of(services.archive_note(ctx, ctx.get(Note, data.id)))
