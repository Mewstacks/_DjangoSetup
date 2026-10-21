# Architecture

```
 Client ── REST /api/v1 ─┐
 Agent ─── MCP /mcp ─────┤  ActionContext (actor, organization, role, scopes, channel, request id)
 Flow ──── Temporal ─────┼─► apps.actions.invoke()
 CLI ───── manage.py ────┘    scope → role → rate limit → validate → idempotency
                              → transaction → audit → undo journal → log
```

## Apps

| App | Role |
|---|---|
| `actions` | The kernel: `@action` registry, runtime, REST and MCP adapters, undo journal, agent ledger |
| `apikeys`, `oauth`, `accounts` | Credentials: API keys, OAuth 2.1 (PKCE, registration policy), allauth sign-in with MFA, staff MFA, key revocation on reset |
| `organizations` | Tenants, memberships, roles, quotas; `OrganizationScopedViewSet`; `OrgScopedPrimaryKeyRelatedField` |
| `flows` | Flows and jobs on Temporal or the local engine; `TemporalTaskBackend` for `django.tasks` |
| `audit` | Append-only, keyed-hash-chained audit trail per organization |
| `privacy` | LGPD: data catalog, consent, cookie consent, requests, retention, incidents, impact assessments, age-assurance seam, RoPA |
| `webhooks`, `flags`, `uploads` | Outbound events with an outbox, feature flags and settings, validated files |
| `observability` | structlog pipeline with redaction, OpenTelemetry, `doctor`, health |
| `common` | Encryption, network guard, logging, middleware, throttling |
| `examples` | Notes: a complete reference resource (remove it with `scripts/remove_example.py`) |
| `devtools` (not an app) | The rulebook, scaffold, convention checks and the development MCP server: [AI guide](guides/ai-development.md) |

## Rules the code enforces

- **One door to tenant data.** Actions read rows only through `ctx.scoped(Model)` / `ctx.get`; a test
  fails on `Model.objects` in `actions.py`, `actions/*.py` and `agent.py`, and another on a model with
  an organization column that is neither scoped nor explained. Writable foreign keys use
  `OrgScopedPrimaryKeyRelatedField`.
- **Default deny for keys.** A key or OAuth token acts only inside its scopes; the role of the
  membership is read on every call, never copied into a token.
- **Every model is classified.** A test fails until each model is declared personal or not in
  `<app>/privacy.py`; another when a personal-looking field is unlisted or sensitive data is not
  encrypted.
- **A write action decides undo.** The app does not start until it says `undoable=True` or why not.
- **No secrets in logs.** Redaction runs at the end of the logging pipeline, so third-party loggers
  are covered as well.
- **Fails closed in production.** `config.settings.production` refuses weak secrets, unverified
  database TLS, plain Redis, wildcard hosts, an undeclared proxy and a missing controller or DPO.
- **The audit trail resists its own application.** Keyed chain, owner-only prune, runtime role that
  cannot rewrite it ([ADR 13](adr/audit-chain-and-role-split.md)).
- **The rules are checked for every action.** The conformance suite is parametrised over the
  registry, so a new action is tested without writing a test.

## Settings modules

`config.settings.base` (shared), `local` (development), `test`, `production` (strict, the image
default). Variables are listed in the [generated reference](reference/env-vars.md).

## Request path in production

Proxy/ingress (TLS) → gunicorn with uvicorn workers → `BodyLimit` ASGI middleware (size and
read timeout) → Django middleware (security headers, request context, admin allow-list, no-store,
sessions, CSRF, staff MFA, organization context, CSP) → DRF (API key, session token or session auth,
scope and role permissions, throttles) → action runtime. `/mcp` is mounted beside Django in the ASGI
app and shares the same pre-flight checks.

## Two MCP servers

`/mcp` lets an agent operate a running product as a person. `python -m devtools.mcp` lets an agent
build the product. They share the registries, nothing else ([ADR 15](adr/two-mcp-servers.md)).
