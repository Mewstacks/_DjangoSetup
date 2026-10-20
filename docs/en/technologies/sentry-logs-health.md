# Sentry, logs, and health checks

[Versão em português](../../pt-BR/tecnologias/sentry-logs-health.md) ·
[Back to the learning path](../learning-path.md)

## Observability

Observability answers: “what failed, for whom, when, and in which release?”

- **Logs:** events written by the application.
- **Sentry:** groups exceptions, stack traces, and performance.
- **Metrics:** values over time, such as latency and errors.
- **Request ID:** connects a response, log lines, and a Sentry event.

## Structured logs

JSON lets tools search fields such as level, request ID, and organization ID. Never log bodies,
cookies, tokens, passwords, or personal data.

Audit and logs differ. Logs support operations; audit records a controlled, immutable business
action.

## Sentry and minimization

The SDK disables default PII, bodies, local variables, and source context. Filters remove known
sensitive fields before sending.

Also configure server-side scrubbers, minimal retention, restricted membership, MFA, separate
environments, and redaction tests with synthetic data. Sentry is a vendor in the LGPD inventory.

## Liveness and readiness

```text
/health/live/  → does the process respond?
/health/ready/ → do PostgreSQL and Redis work?
```

Fly avoids routing traffic to unready instances. A short per-worker readiness cache protects
dependencies. Health checks do not replace alerts: a system may return `200` while slow, missing
workers, or accumulating tasks.

Monitor error rate, p95/p99 latency, releases, database connections, Redis memory, queue age, task
failures, storage, and lockouts. Every alert needs an owner and runbook action.
