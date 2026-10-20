from __future__ import annotations

from contextvars import ContextVar

# Ambient request/flow context. Everything that logs reads these; everything that crosses a
# process boundary (HTTP -> Temporal -> activity, MCP, CLI) sets them first.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
organization_id_var: ContextVar[str | None] = ContextVar("organization_id", default=None)
actor_id_var: ContextVar[str | None] = ContextVar("actor_id", default=None)
channel_var: ContextVar[str | None] = ContextVar("channel", default=None)
workflow_id_var: ContextVar[str | None] = ContextVar("workflow_id", default=None)
activity_var: ContextVar[str | None] = ContextVar("activity", default=None)

LOG_CONTEXT_VARS: dict[str, ContextVar[str | None]] = {
    "request_id": request_id_var,
    "organization_id": organization_id_var,
    "actor_id": actor_id_var,
    "channel": channel_var,
    "workflow_id": workflow_id_var,
    "activity": activity_var,
}
