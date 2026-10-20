# Add an action

An action is a function `fn(ctx, data) -> result` with pydantic input and output. Declaring it
creates, with no further code, `POST /api/v1/actions/<name>/`, an MCP tool, a Temporal activity
and a CLI command, all under the same scope, role, rate-limit, idempotency and audit rules.

```python
# src/apps/tasks/actions.py   (any installed app; modules named actions.py are discovered)
from pydantic import BaseModel, Field
from apps.actions.context import ActionContext
from apps.actions.registry import action
from apps.tasks.models import Task


class CreateTask(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class TaskOut(BaseModel):
    id: str
    title: str


@action("tasks.create", write=True)
def create_task(ctx: ActionContext, data: CreateTask) -> TaskOut:
    """Create a task in the current organization."""  # this text is the MCP tool description
    task = Task.objects.create(organization=ctx.organization, title=data.title)
    return TaskOut(id=str(task.id), title=task.title)
```

Rules checked at startup: the name is `domain.verb` and unique; the docstring is not empty; a write
action does not use a `:read` scope; input and output are pydantic models. Options:
`scope=`, `write=`, `channels={"api","mcp","flow","cli"}`, `roles=`, `idempotent=`,
`destructive=` (MCP hint), `undo=` (see below).

## Checklist for a new resource

1. Model: subclass `OrganizationScopedModel`.
2. `<app>/privacy.py`: `personal(...)` or `not_personal(..., reason)`. The test suite fails otherwise.
3. Read through `ctx.scoped(Model)` or `ctx.get(Model, id)`; never `Model.objects` inside actions.
4. Emit an event if outsiders care: `register_event` in `<app>/events.py` and
   `emit("task.created", org, {"task_id": ...})` inside the same transaction.
5. Regenerate the committed artifacts: `python manage.py actions_catalog`,
   `python scripts/check_openapi.py --write`, `python scripts/gen_docs.py`.
6. Test with the API client; the auth matrix test also covers the new action's scope.

## Undo

Pass an undo handler so agents can reverse their own changes (`actions.changes`,
`actions.undo`). The journal stores before/after snapshots encrypted and refuses an undo when the
row was edited afterwards. See `apps/examples/undo.py`.

## Scopes

A scope is `domain:level`. New ones appear in the catalog automatically; extra scopes without
actions come from `ACTIONS_EXTRA_SCOPES`. The same scope vocabulary serves API keys, OAuth
consent and MCP.

Remove the example: delete `apps/examples`, its entry in `LOCAL_APPS`, its tests and rerun the
generators.
