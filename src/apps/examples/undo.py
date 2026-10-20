"""How to take back each change the notes actions make."""

from __future__ import annotations

from django.db.models import Model

from apps.actions.context import ActionContext
from apps.actions.journal import expect_unchanged, snapshot, undo_handler
from apps.actions.models import ActionJournal
from apps.examples.models import Note
from apps.examples.services import SNAPSHOT_FIELDS


def _note(row: Model) -> Note:
    assert isinstance(row, Note)
    return row


@undo_handler(Note, "create")
def undo_create(ctx: ActionContext, entry: ActionJournal, row: Model) -> None:
    """A created note is archived, not deleted: the audit trail keeps pointing at a real row."""
    from django.utils import timezone

    note = _note(row)
    expect_unchanged(entry, snapshot(note, SNAPSHOT_FIELDS))
    note.archived_at = timezone.now()
    note.save(update_fields=["archived_at", "updated_at"])


@undo_handler(Note, "update")
def undo_update(ctx: ActionContext, entry: ActionJournal, row: Model) -> None:
    note = _note(row)
    expect_unchanged(entry, snapshot(note, SNAPSHOT_FIELDS))
    note.title = entry.before["title"]
    note.body = entry.before["body"]
    note.save(update_fields=["title", "body", "updated_at"])


@undo_handler(Note, "archive")
def undo_archive(ctx: ActionContext, entry: ActionJournal, row: Model) -> None:
    note = _note(row)
    expect_unchanged(entry, snapshot(note, SNAPSHOT_FIELDS))
    note.archived_at = None
    note.save(update_fields=["archived_at", "updated_at"])
