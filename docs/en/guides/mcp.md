# MCP server

Every action whose channels include `mcp` is a tool. The server is stateless streamable HTTP
mounted at `MCP_PATH` (default `/mcp`), optionally per organization at `/mcp/<org-slug>`.
(To let an agent *build* the product instead, see [Building with an AI coding agent](ai-development.md).)

```bash
MCP_ENABLED=true  MCP_PUBLIC_URL=https://app.example.com
python manage.py mcp_config --url https://app.example.com --org acme
```

`mcp_config` prints ready-to-paste snippets for Claude Code, Cursor/VS Code JSON and a curl check.
It never prints a real secret.

## Protocol

Stateless: no session, any replica answers any request (`Mcp-Session-Id` is never issued). The
server answers `initialize` for the revisions 2025-03-26, 2025-06-18 and 2025-11-25 and serves a
client that never initializes, which is how the 2026-07-28 revision works. A test pins this, so an
SDK upgrade cannot change it quietly. Tool names are `<action>` with dots turned into underscores
(`notes.create` is `notes_create`, optionally prefixed by `MCP_TOOL_PREFIX`); the
[reference](../reference/actions.md) lists both.

## Authentication

- **API key**: `Authorization: Bearer <key>`; scopes limit the tools listed and callable.
- **OAuth 2.1** (`OAUTH_ENABLED=true`): authorization code flow with PKCE. Metadata:
  `/.well-known/oauth-authorization-server` and `/.well-known/oauth-protected-resource`.
  - Tokens are audience-bound to the MCP URL (RFC 8707); a token with no audience is refused.
  - Tokens are stored as a SHA-256 checksum, not in clear (a database dump holds nothing
    replayable); refresh tokens rotate and a replay revokes the family; authorization responses
    carry `iss` (RFC 9207).
  - **Registration.** Dynamic client registration is on but throttled and off for anonymous callers
    unless `OAUTH_DCR_ANONYMOUS=true`. A registration is refused unless it asks only for the
    `authorization_code` / `refresh_token` grants and its redirect URIs are `https`, an `http`
    loopback address (`127.0.0.1`, `::1`, `localhost`) or a scheme listed in
    `OAUTH_REDIRECT_URI_SCHEMES` (for example `cursor://`); no wildcards, fragments or more than
    five. The registration token expires (`OAUTH_DCR_REGISTRATION_TOKEN_SECONDS`, 30 days).
  - **Client ID Metadata Documents** (the registration method the 2026-07-28 revision prefers over
    DCR): `OAUTH_CIMD_ENABLED=true` lets a client use an `https` URL as its `client_id`, fetched
    through an SSRF-hardened fetcher; `OAUTH_CIMD_ALLOWED_HOSTS` narrows it. Off by default.

## What agents get

- Tools generated from the pydantic schemas, with `readOnlyHint`/`destructiveHint` derived from
  the action, so they cannot disagree with `write`.
- `platform://actions`, `platform://scopes` and the `how_to_use_platform` prompt (scope
  `platform:read`, included in every read profile): what this credential may call, its role and
  limits, and how to behave (act as the person, say what you change, ask before anything
  destructive, treat record text as data). Add your own with `<app>/agent.py`.
- Every call is audited with channel `mcp`; writes keep an undo snapshot
  (`ACTIONS_JOURNAL_CHANNELS`, kept `ACTIONS_JOURNAL_RETENTION_DAYS`). Each write action declares
  whether it can be undone (`undoable`); the catalog shows it.
- `agent.report` records time spent by the agent in a ledger (`AgentRun`).

## Operational notes

- The MCP app does not pass through Django middleware, so it has its own pre-flight: trusted
  client IP, request id, per-IP budget (`MCP_RATE_PER_MINUTE_IP`), body cap, Host/Origin guard
  (`MCP_ALLOWED_ORIGINS`).
- A key's IP allow-list is checked against the real client address, also on `/mcp`.
- No CORS by default; browsers are not MCP clients.
- A parity test asserts the same action over REST and MCP produces the same audit fields.
