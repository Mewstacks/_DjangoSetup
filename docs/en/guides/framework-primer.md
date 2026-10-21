# Framework primer

What a developer (or an AI agent) needs to know about Django and the libraries around it to
program correctly on this platform. Each section says how the thing works, then the rule this
project adds. Official documentation for the versions in `pyproject.toml`: Django 6.1
(<https://docs.djangoproject.com/en/6.1/>), DRF (<https://www.django-rest-framework.org/>),
django-allauth (<https://docs.allauth.org/>), Temporal Python SDK
(<https://docs.temporal.io/develop/python>), FastMCP (<https://gofastmcp.com/>).

## Request cycle and middleware

A request enters the ASGI app, passes the middleware list **top to bottom**, reaches the view,
and the response travels back **bottom to top**. A middleware that returns early (a refusal)
skips everything below it. Order is therefore a security decision, and `settings.MIDDLEWARE` is
the only place it is set. Call the `middleware_stack` tool for the live order with a note on each.

Rules here:

- `SecurityMiddleware` and `SecurityHeadersMiddleware` come first so every response, including
  refusals, carries the headers.
- `RequestContextMiddleware` runs before anything that logs, so every line has a request id.
- Authentication (`AuthenticationMiddleware`) must precede `OrganizationContextMiddleware`,
  which reads `request.user` to resolve the tenant from `X-Organization-ID`.
- A new middleware goes where its dependencies are already populated and before anything that
  needs its result. State the reason in a comment above the entry.
- `/mcp` is mounted beside Django in the ASGI app and does **not** pass through this list; it has
  its own pre-flight (`apps.actions.mcp.preflight`). A control added to middleware must be added
  there too, or it does not cover MCP.

## ORM, models and migrations

- Tenant models subclass `OrganizationScopedModel` and are read through `ctx.scoped(Model)` /
  `ctx.get`. Never `Model.objects` for tenant rows in actions.
- Every model is classified in `<app>/privacy.py` (LGPD); the test suite fails until it is.
- Start from `UUIDTimeStampedModel` (UUID primary key, `created_at`, `updated_at`); datetimes are
  timezone-aware (`USE_TZ`).
- `makemigrations` after every model change; never edit a migration that has shipped; keep data
  migrations idempotent. The migrations run as the schema owner, the web process runs as a
  role that cannot alter schema (see the audit ADR).
- Avoid N+1 queries: `select_related` for foreign keys, `prefetch_related` for reverse sets.
  Do not filter on an `EncryptedTextField`; use `blind_index()` for equality.

## Transactions and signals

- An action runs in one transaction (`ATOMIC_REQUESTS` is not used); the audit event is written
  inside it so it cannot exist without the change.
- Side effects that leave the database (e-mail, webhook, task) go through
  `transaction.on_commit` or the webhook outbox, never directly inside the transaction.
- Signals are for cross-app reactions already in the codebase (audit, uploads cleanup). Business
  rules do not go in signals: put them in `services.py` where REST, MCP, CLI and Temporal share
  them.

## Django REST Framework

- Operations are actions; classic CRUD may use `OrganizationScopedViewSet` in `api.py`.
- Permissions: `IsAuthenticated`, `HasOrganizationContext`, `RoleCanWrite`, and
  `ApiKeyScopePermission` for keys. A viewset that lacks them is a bug the tests catch.
- Writable foreign keys use `OrgScopedPrimaryKeyRelatedField` so an id from another tenant is
  refused.
- Errors use one envelope for every surface; raise `DomainError` subclasses (`NotFound`,
  `Forbidden`, `Invalid`, `Conflict`), never leak Django `ValidationError` text.

## Accounts, sessions and MFA

- Sign-in, e-mail verification and MFA are django-allauth (headless). Lockout is django-axes.
- Staff need MFA for `/admin/`; owners and admins need it in production
  (`ORG_PRIVILEGED_MFA_REQUIRED`), enforced in the DRF permission and in the action runtime.
- API keys and OAuth tokens act only within their scopes; the role is read from the membership on
  every call. Minting a key needs a recent sign-in.

## Settings

Four modules: `base`, `local`, `test`, `production`. Add configuration with
`env_str/env_int/env_bool/env_list` and a comment above it; the environment reference is
generated from these calls. Production-only constraints live in
`config/settings/validators.py`; never loosen one.

## Templates and CSP

The few server-rendered pages (sign-in, MFA, consent, OAuth) are CSP-clean: no inline script or
style, no third-party origin. `{# #}` comments are single-line only; use
`{% comment %}` for more.

## Temporal (flows and jobs)

- A **workflow** is deterministic code that is replayed from history: no Django ORM, no network,
  no `datetime.now()`, no random. Call actions through `apps.flows.sdk.call_action`.
- An **activity** is a normal sync function that does the work; payloads are sealed (encrypted)
  and carry ids, not documents.
- A **job** is a function on a cron schedule (Temporal Schedule, or `run_scheduler` when Temporal
  is off). `manage.py flows_sync` creates or updates Schedules after a deploy.
- Changing a workflow that may be running needs `workflow.patched`; keep replay histories in
  tests.
- With Temporal off the local engine runs the same flows; not every flow is portable and the
  capability matrix says which.

## Background tasks (`django.tasks`)

`TemporalTaskBackend` runs declared tasks on Temporal, the immediate backend runs them inline.
Only tasks under `FLOWS_TASK_MODULE_PREFIXES` are allowed. Pass ids, not model instances.

## Testing

`pytest` with `pytest-django`. Use the fixtures in `tests/conftest.py` (`org_client`,
`other_org_client`). A new action needs a test for its scope, a read-only role and a cross-tenant
attempt; the conformance suite already runs every registered action through the standard checks.

## MCP (FastMCP)

Two servers, two jobs: `/mcp` operates a running product; `python -m devtools.mcp` builds it.
Tools are actions; resources and prompts live in `agent.py`. A tool description is a prompt: write
it for the model that will read it.
