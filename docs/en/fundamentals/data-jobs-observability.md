# Data, jobs, and observability

[Versão em português](../../pt-BR/fundamentos/dados-jobs-observabilidade.md) ·
[Back to the summary](../technologies-and-middleware.md)

## PostgreSQL: the source of truth

PostgreSQL stores data that must survive: users, organizations, consent, audit records, and
product data.

- **Transaction:** saves everything or nothing.
- **Constraint:** prevents invalid states inside the database.
- **Index:** accelerates reads at a storage and write cost.
- **Migration:** changes the schema reproducibly.

Backups, encryption at rest, and restore tests remain operational responsibilities.

## Redis: fast and temporary

Redis stores cache, accelerated sessions, throttle/Axes counters, and the Celery queue. It is fast
because it works mainly in memory.

Do not keep the only copy of important data there. If Redis fails, the application should expose
the failure and recover without losing business records.

## Celery: background work

Use Celery when work need not finish before the response:

```text
Request → create job → return 202
Celery worker → process → save result
```

Examples include email, LGPD exports, webhooks, and reports. Pass IDs to a task, not bundles of
personal data.

Tasks may execute more than once after failures. Make them **idempotent**, limit retries and
execution time, and persist state in PostgreSQL.

## Object storage: files

A Fly Machine filesystem is ephemeral. Uploads and exports belong in a private bucket such as
Tigris/S3.

- validate type and size;
- use unpredictable names;
- authorize uploads and downloads;
- generate expiring signed URLs;
- define retention and data location.

## Sentry and logs: observability

**Observability** means understanding the system through errors, logs, and metrics.

The request ID connects a response to logs and a Sentry event. The project removes known cookies,
tokens, bodies, and personal data before sending them.

Even so:

- avoid logging sensitive data at the source;
- keep scrubbers in Sentry as well;
- use minimal retention;
- restrict project access;
- never debug production by collecting complete data.

Sentry reports a technical error; audit records a business action. Neither replaces the other.

## Health checks

- **Liveness:** is the process responding?
- **Readiness:** are PostgreSQL and Redis ready for traffic?

Fly uses these responses when routing requests. Readiness is not complete monitoring: also watch
error rate, latency, database connections, and queue size.

## Quick choice

| Need | Tool |
| --- | --- |
| Permanent record | PostgreSQL |
| Fast temporary value | Redis |
| Slow work | Celery |
| Upload or export | Object storage |
| Technical error | Sentry/logs |
| Who performed an action | Audit |

Do not add infrastructure because it is fashionable. Start simple and scale from real metrics and
risks.
