from apps.actions.models import ActionJournal, AgentRun, IdempotencyRecord
from apps.privacy.catalog import Category, by_user, personal

personal(
    ActionJournal,
    resolver=by_user(ActionJournal, "user"),
    fields={
        "label": Category.CONTENT,
        "before_json": Category.CONTENT,
        "after_json": Category.CONTENT,
    },
    purpose="security-and-audit",
    retention_field="created_at",
    on_erase="delete",
)
personal(
    AgentRun,
    resolver=by_user(AgentRun, "user"),
    fields={"summary": Category.CONTENT, "note": Category.CONTENT},
    purpose="security-and-audit",
    retention_field="started_at",
    on_erase="delete",
)
personal(
    IdempotencyRecord,
    resolver=None,
    fields={"response_json": Category.CONTENT},
    purpose="product-content",
    retention_field="created_at",
    on_erase="delete",
    reason="Replayable responses; pruned after 24 hours by maintenance.prune_idempotency.",
)
