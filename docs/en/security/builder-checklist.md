# Builder's checklist: security and LGPD for every change

Run through the section that matches what you are adding. Each line says what to do and what
enforces it, so you know which items a green gate already covers.

## A new model

- [ ] Tenant data subclasses `OrganizationScopedModel` (test: every organization column is scoped or
      explained).
- [ ] `<app>/privacy.py`: `personal(...)` with every personal-looking field listed, or
      `not_personal(..., "why")` (tests: `test_lgpd`, `test_catalog_lint`).
- [ ] Free text that can hold personal data is `EncryptedTextField`; sensitive and child data must be.
- [ ] You know the purpose, the erase rule and the retention clock (`lgpd_check` walks you through).
- [ ] Added an index for the way you query (always `organization` first).

## A new action or endpoint

- [ ] Reads through `ctx.scoped` / `ctx.get`; never `Model.objects` (AST test).
- [ ] Docstring written for the model that reads it; scope; `write` / `destructive` / `undoable`
      declared (import-time check); `roles=` if only some roles may.
- [ ] Input is a pydantic model with bounds (`max_length`, `ge`, `le`); output never carries a
      field named like a secret (conformance test).
- [ ] Refusals are `DomainError`s with a caller-readable message.
- [ ] A test for the scope, a read-only role and another tenant (the conformance suite does the
      first two for you).
- [ ] If tenants can create the resource without bound, it calls `organizations.quotas`.

## Anything that reaches the network

- [ ] A URL somebody else chose goes through `apps.common.netguard` (https only, public addresses
      only, pinned IP, no redirects, bounded time and size).
- [ ] A fixed provider URL still verifies TLS. Never `verify=False`.
- [ ] Credentials come from settings, not code; secrets are never logged.

## A new setting or secret

- [ ] `env_*` helper with a comment above it (it becomes the reference docs).
- [ ] If production must constrain it, add a validator in `config/settings/validators.py` and a
      test; a missing or weak value must stop the boot with a message that names the variable.
- [ ] Added to `deploy/compose/prod.env.example` and the Kubernetes `configmap`/`secret` examples.

## A new page or template

- [ ] No inline script or style and no third-party origin (CSP is `'self'`).
- [ ] Forms are CSRF-protected; destructive links are POST.
- [ ] Copy is a label or a verb, not a paragraph that explains the screen.

## Logging, audit and errors

- [ ] Audit metadata: snake_case keys, ids and counts, no personal values (validated at write).
- [ ] No request bodies, tokens or addresses in logs (redaction is the net, not the plan).
- [ ] Internal errors reach the client as `server_error` plus `request_id`, nothing more.

## Background work

- [ ] Workflows import no Django; the work is an action called through `call_action`.
- [ ] A cron-style job is `@job` with a schedule; it is idempotent.
- [ ] A new webhook event is `register_event` and its payload carries ids only.

## Before you push

- [ ] `python scripts/verify.py` (full) is green.
- [ ] Generated files fresh: `actions_catalog`, `check_openapi.py --write`, `gen_docs.py`.
- [ ] Docs updated in `docs/en` **and** `docs/pt-BR`; `CHANGELOG.md` for anything a user sees.
- [ ] Nothing weakened to make a test pass (validators, CORS, `NETGUARD_ALLOW_PRIVATE`, `DEBUG`).
- [ ] For anything about the ANPD, children, or international transfers: a person with legal
      standing has looked at it.
