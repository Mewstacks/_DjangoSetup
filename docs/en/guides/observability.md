# Observability

## Logs

structlog on top of the standard library: one JSON pipeline for application and third-party
loggers. Every line carries `request_id` (generated server-side; a client-sent id is kept in a
separate field), `organization_id`, `actor_id`, channel and, inside Temporal, workflow and
activity ids. Redaction (e-mail, CPF/CNPJ, phone, IP, tokens, API keys, cookies, URLs with
passwords, exception text) runs at the **end** of the pipeline. A golden-log test fails when
synthetic personal data reaches output. Level: `LOG_LEVEL` (DEBUG is refused in production).

## Traces and metrics

`OTEL_ENABLED=true` with the `otel` extra exports OTLP for Django, psycopg, httpx and Temporal.
Locally: `docker compose --profile observability up` then open Grafana on port 3000. Sentry stays
optional (`SENTRY_ENABLED`), with scrubbing applied.

## Health and `doctor`

`/api/v1/health/live/` is process-only. `/api/v1/health/ready/` checks database and cache and
reports worker state informationally. `python manage.py doctor [--strict]` also checks encryption,
proxy declaration, HTTPS posture, e-mail and Temporal reachability; run it in CD.
`python manage.py audit_verify` checks the audit chains.
