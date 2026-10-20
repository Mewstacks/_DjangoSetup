# Architecture

[Versão em português](../pt-BR/arquitetura.md)

The starter is a modular monolith. That is deliberate: database transactions, privacy
operations, migrations, and authorization remain understandable while the web and worker
processes scale horizontally. Split services only after measurements show a real boundary.

## Runtime

- `web`: stateless Django ASGI instances behind Fly Proxy. Session state, throttles, and caches
  live in Redis; persistent data lives in PostgreSQL or private object storage.
- `worker`: Celery consumers using the same image and code. Tasks must be idempotent, retry with
  bounded exponential backoff, and receive record IDs rather than personal-data payloads.
- Managed PostgreSQL: primary source of truth, pooled connections, HA, backups, encryption in
  transit and at rest.
- Redis: cache, session acceleration, authentication lockouts, throttles, and queue broker.
  Redis is never the source of truth for business or privacy records.
- Private object storage: user-generated files and privacy exports through short-lived signed
  URLs. Never serve uploads from the application origin.
- Sentry and JSON logs: operational telemetry with PII disabled/scrubbed and request IDs for
  correlation.

The public readiness endpoint memoizes results per worker for five seconds, reducing PostgreSQL
and Redis load without depending on Redis-backed throttling.

## Application boundaries

- `accounts`: identity only. Add OIDC/passkeys here without coupling it to product domains.
- `organizations`: optional tenant, membership, roles, context middleware, and the abstract
  `OrganizationScopedModel`.
- `privacy`: processing purposes, notices, consent ledger, subject requests, and incident
  records. Product apps register their own export/erasure logic rather than using unsafe
  reflection-based deletion.
- `audit`: immutable security/business events. Metadata keys that commonly contain PII or
  secrets are rejected.
- `common`: encryption, request context, error envelope, health checks, safe logging, and
  Sentry scrubbing.

## Tenant invariant

An organization UUID supplied by the client is only a selector. Middleware resolves it through
the authenticated user's active membership and returns `404` on failure. Product endpoints
must then require organization context and scope reads/writes to `request.organization`. Global
objects such as users, privacy purposes, and notices are intentionally outside tenant scope.

Organization listing resolves the current role with a subquery/annotation rather than loading
every member. Query count remains bounded as membership grows.

For products with high tenant-isolation risk, add PostgreSQL row-level security as a second
layer after the product schema is known. Do not add generic RLS policies that can silently
bypass background jobs or migrations.

## Scale path

1. Increase web/worker Machines independently and keep database/Redis in `gru`.
2. Measure p95 latency, query count, queue age, database CPU/connections, and error rate.
3. Add indexes from real query plans; cache only safe, non-sensitive derived values.
4. Introduce read replicas or regional services only when consistency and international
   transfer implications are explicitly designed.
5. Extract a service only when it has an independent scaling, ownership, or failure boundary.
