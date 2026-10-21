# ADR 14: Row-level security is an opt-in design, not the default

**Status:** accepted as a documented option. **Not implemented.**

## Context

Tenant isolation today is by construction: actions read only through `ctx.scoped`/`ctx.get`, the
viewset base filters by organization, writable foreign keys are validated against the organization,
and tests scan the code and exercise cross-tenant access. That is convention, enforced by tests. A
bug that bypasses it (a raw query, a forgotten filter in code outside `actions.py`) leaks across
tenants. PostgreSQL row-level security (RLS) would make the database refuse such a read.

## Options

1. **Convention plus tests** (today). Cheap, portable (SQLite in tests), the failure mode is a bug.
2. **RLS on tenant tables.** A policy `USING (organization_id = current_setting('app.org')::uuid)`,
   with the setting made by `SET LOCAL` at the start of each transaction.

## Decision

Keep option 1 as the default and document option 2 so a team that needs it can adopt it without a
redesign. Reasons for not defaulting to it:

- Every request and background task must set the organization on its connection, inside a
  transaction, or PgBouncer in transaction-pooling mode leaks it to the next client.
- Migrations, the admin, system jobs and the audit chain (null organization) need a bypass role,
  which is one more privileged path to guard.
- Two code paths to test (SQLite without RLS, PostgreSQL with), and a measurable planner cost.

## If you adopt it

1. Run the application as a role without `BYPASSRLS` (the runtime role already differs from the
   owner; see ADR 13).
2. `ALTER TABLE <t> ENABLE ROW LEVEL SECURITY; ALTER TABLE <t> FORCE ROW LEVEL SECURITY;` and one
   policy per table on `organization_id`, with `WITH CHECK` for writes.
3. Set `app.org` with `SET LOCAL` where `ActionContext` is built and in
   `OrganizationContextMiddleware`; a request without an organization sets it to the nil UUID so
   nothing matches.
4. Give system jobs a separate role with an explicit policy for rows whose organization is null.
5. Run `tests/test_tenant_isolation.py` and the conformance suite against PostgreSQL with RLS on.

Start with the tables that hold the most sensitive data (uploads, webhooks, API keys).
