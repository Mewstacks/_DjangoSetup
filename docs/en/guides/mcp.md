# MCP server

Every action whose channels include `mcp` is a tool. The server is stateless streamable HTTP
mounted at `MCP_PATH` (default `/mcp`), optionally per organization at `/mcp/<org-slug>`.

```bash
MCP_ENABLED=true  MCP_PUBLIC_URL=https://app.example.com
python manage.py mcp_config --url https://app.example.com --org acme
```

`mcp_config` prints ready-to-paste snippets for Claude Code, Cursor/VS Code JSON and a curl check.
It never prints a real secret.

## Authentication

- **API key**: `Authorization: Bearer <key>`; scopes limit the tools listed and callable.
- **OAuth 2.1** (`OAUTH_ENABLED=true`): clients use the authorization code flow with PKCE;
  dynamic client registration is on but throttled and off for anonymous callers unless
  `OAUTH_DCR_ANONYMOUS=true`. Tokens are audience-bound to the MCP URL (RFC 8707). Metadata:
  `/.well-known/oauth-authorization-server` and `/.well-known/oauth-protected-resource`.

## What agents get

- Tools generated from the pydantic schemas, with `readOnlyHint`/`destructiveHint` derived from
  the action, so they cannot disagree with `write`.
- Every call is audited with channel `mcp`; writes keep an undo snapshot
  (`ACTIONS_JOURNAL_CHANNELS`, kept `ACTIONS_JOURNAL_RETENTION_DAYS`).
- `agent.report` records time spent by the agent in a ledger (`AgentRun`).

## Operational notes

- The MCP app does not pass through Django middleware, so it has its own pre-flight: trusted
  client IP, request id, per-IP budget (`MCP_RATE_PER_MINUTE_IP`), body cap, Host/Origin guard
  (`MCP_ALLOWED_ORIGINS`).
- No CORS by default; browsers are not MCP clients.
- A parity test asserts the same action over REST and MCP produces the same audit fields.
