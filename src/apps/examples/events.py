from apps.webhooks.events import register_event

register_event("note.created", "A note was created. Data: note_id.")
register_event("note.archived", "A note was archived. Data: note_id.")
