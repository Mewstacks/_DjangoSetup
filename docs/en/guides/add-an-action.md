# Add an action

An action is a function `fn(ctx, data) -> result` with pydantic input and output. Declaring it with
`@action` records the contract (name, scope, whether it writes) and nothing else: REST, MCP, the CLI
and Temporal are adapters over the registry, so one function is four integrations.

**Fastest path:** `python manage.py scaffold resource invoices Invoice --fields 'title:str,amount:decimal'`
generates a complete resource that already follows every rule on this page (see
[Start a product](start-a-product.md)). Read on to understand, or to add one action to an existing app.

```python
# <app>/actions.py  (discovered automatically)
from pydantic import BaseModel
from apps.actions.context import ActionContext
from apps.actions.registry import action


class CreateTask(BaseModel):
    title: str


class TaskOut(BaseModel):
    id: str
    title: str


@action("tasks.create", write=True, undoable=True)
def create_task(ctx: ActionContext, data: CreateTask) -> TaskOut:
    """Create a task in the caller's organization. Send an Idempotency-Key to make retries safe."""
    task = services.create_task(ctx, title=data.title)  # business rules live in services.py
    return TaskOut(id=str(task.id), title=task.title)
```

Rules checked when the app starts (they fail at startup, not in production):

- the name is `domain.verb` and unique;
- the docstring is non-empty: it is what a model reads as the tool description;
- a write action's scope is not a `:read` scope;
- **a write action says whether it can be undone**: `undoable=True` (with a handler, see below) or
  `undoable="<why it cannot be>"`;
- `data` and the return value are pydantic models.

Options: `scope=`, `write=`, `channels={"api","mcp","flow","cli"}`, `roles=`, `idempotent=`,
`destructive=` (MCP hint), `audit=`, `undoable=`, `title=`.

## Checklist for a new resource

1. Model: subclass `OrganizationScopedModel`.
2. `<app>/privacy.py`: `personal(...)` or `not_personal(..., reason)`. The test suite fails otherwise,
   and also when a personal-looking field is not listed or a sensitive one is not encrypted.
3. Read through `ctx.scoped(Model)` or `ctx.get(Model, id)`; never `Model.objects` inside actions.
4. Emit an event if outsiders care: `register_event` in `<app>/events.py` and
   `emit("task.created", org, {"task_id": ...})` inside the same transaction.
5. Record changes for undo: `ctx.record_change(...)` and `ctx.set_target(row)` in the service.
6. Regenerate the committed artifacts: `python manage.py actions_catalog`,
   `python scripts/check_openapi.py --write`, `python scripts/gen_docs.py`.
7. Test it. The conformance suite already checks scope, read-only roles, unlisted channels and bad
   input for **every** action; add the cross-tenant and business cases.

## Undo

`undoable=True` means an undo handler reverses the change, so agents can take back their own work
(`actions.changes`, `actions.undo`). Put handlers in `<app>/undo.py` (discovered automatically): the
journal stores before/after snapshots encrypted and refuses an undo when the row was edited
afterwards. See `apps/examples/undo.py`. Actions that cannot be undone give the reason as the value
of `undoable` (for example "a delivered signal cannot be recalled").

## Scopes

A scope is `domain:level`. New ones appear in the catalog automatically; extra scopes without
actions come from `ACTIONS_EXTRA_SCOPES`. The same scope vocabulary serves API keys, OAuth consent
and MCP. See [roles and permissions](roles-and-permissions.md).

## Removing the example

`python scripts/remove_example.py` deletes `apps/examples`, unwires it and lists the tests that still
use Notes, which you port to your own resource.
