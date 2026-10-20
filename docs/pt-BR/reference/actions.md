# Ações e ferramentas MCP

> Gerado por `python scripts/gen_docs.py`. Não edite à mão.

| Ação | Escopo | Escreve | Canais | Descrição |
|---|---|---|---|---|
| `actions.changes` | `actions:read` | não | api, cli, flow, mcp | List the caller's recent changes, newest first, with ids that `actions.undo` accepts. |
| `actions.undo` | `actions:write` | sim | api, cli, flow, mcp | Take back one of your own changes. Refuses if the record was edited after it. |
| `agent.report` | `actions:write` | sim | mcp | Attach a summary and your model name to the current working session (optional). |
| `flags.evaluate` | `flags:read` | não | api, cli, flow, mcp | Which feature flags are on for you in this organization. |
| `flows.cancel` | `flows:write` | sim | api, cli, flow, mcp | Cancel a running flow (Temporal engine only). |
| `flows.catalog` | `flows:read` | não | api, cli, mcp | Which engine runs flows here, which flows exist, and what each engine can and cannot do. |
| `flows.runs` | `flows:read` | não | api, cli, flow, mcp | List recent flow runs of this organization. |
| `flows.signal` | `flows:write` | sim | api, cli, flow, mcp | Send a signal to a running flow (Temporal engine only). |
| `flows.start` | `flows:write` | sim | api, cli, flow, mcp | Start one of the flows marked startable. Safe to call with an Idempotency-Key. |
| `flows.status` | `flows:read` | não | api, cli, flow, mcp | Current status of one run (refreshed from Temporal when that engine ran it). |
| `notes.archive` | `notes:write` | sim | api, cli, flow, mcp | Archive a note. Archived notes are hidden from the default list and read-only. |
| `notes.create` | `notes:write` | sim | api, cli, flow, mcp | Create a note. Send an Idempotency-Key to make retries safe. |
| `notes.get` | `notes:read` | não | api, cli, flow, mcp | Read one note by id. |
| `notes.list` | `notes:read` | não | api, cli, flow, mcp | List the organization's notes, newest first. |
| `notes.update` | `notes:write` | sim | api, cli, flow, mcp | Change a note's title or body. Archived notes cannot be edited. |
| `settings.get` | `flags:read` | não | api, cli, flow, mcp | The effective value of a runtime setting for this organization. |
