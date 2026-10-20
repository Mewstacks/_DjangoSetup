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
| `apikeys`, `oauth`, `accounts` | Credentials: API keys, OAuth 2.1 (PKCE, dynamic registration), allauth sign-in with MFA |
| `organizations` | Tenants, memberships, roles; `OrganizationScopedViewSet`; `OrgScopedPrimaryKeyRelatedField` |
| `flows` | Flows and jobs on Temporal or the local engine; `TemporalTaskBackend` for `django.tasks` |
| `audit` | Append-only, hash-chained audit trail per organization |
| `privacy` | LGPD: data catalog, consent, requests, retention, incidents, RoPA |
| `webhooks`, `flags`, `uploads` | Outbound events with an outbox, feature flags and settings, validated files |
| `observability` | structlog pipeline with redaction, OpenTelemetry, `doctor`, health |
| `examples` | Notes: a complete reference resource (remove it with the checklist in the add-an-action guide) |

## Rules the code enforces

- **One door to tenant data.** Actions read rows only through `ctx.scoped(Model)` / `ctx.get`;
  a test fails on `Model.objects` in `actions.py`. Writable foreign keys use
  `OrgScopedPrimaryKeyRelatedField`.
- **Default deny for keys.** A key or OAuth token acts only inside its scopes; the role of the
  membership is read on every call, never copied into a token.
- **Every model is classified.** A test fails until each model is declared personal or not in
  `<app>/privacy.py`.
- **No secrets in logs.** Redaction runs at the end of the logging pipeline, so third-party
  loggers are covered as well.
- **Fails closed in production.** `config.settings.production` refuses weak secrets, plain
  database or Redis transport, wildcard hosts and an undeclared proxy.

## Settings modules

`config.settings.base` (shared), `local` (development), `test`, `production` (strict, the image
default). Variables are listed in the [generated reference](reference/env-vars.md).

## Request path in production

Proxy/ingress (TLS) → gunicorn with uvicorn workers → `BodyLimit` ASGI middleware → Django
middleware (request context, admin allow-list, sessions, CSRF, organization context, CSP) → DRF
(API key, session token or session auth, scope and role permissions, throttles) → action runtime.
`/mcp` is mounted beside Django in the ASGI app and shares the same pre-flight checks.
