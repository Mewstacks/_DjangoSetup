# Fly.io deployment

[Versão em português](../pt-BR/deploy-fly.md)

## Provisioning

1. Configure a unique app name with `scripts/configure_fly.py`, create the app, and keep its
   primary region as `gru`.
2. Import generated Django/encryption secrets through stdin. Store an offline recovery copy of
   field-encryption keys in an approved password manager; Fly only shows secret digests later.
3. Create Fly Managed Postgres in `gru` and attach it. The attached `DATABASE_URL` is pooled.
4. Create Upstash Redis in `gru`; set its private URL as `REDIS_URL`, `CELERY_BROKER_URL`, and
   `CELERY_RESULT_BACKEND`. A fixed-price plan is preferable for continuously polling Celery
   workers.
5. Create a private Tigris bucket. For strict regional residency, substitute a Brazilian-region
   S3-compatible provider and set `AWS_ENDPOINT_URL_S3`, `AWS_REGION`, `BUCKET_NAME`, and its
   credentials.
6. Set `SENTRY_DSN` as a Fly secret. Use separate Sentry projects for production and staging.
   Production fails closed when Sentry is enabled without a DSN. Only set
   `SENTRY_ENABLED=false` as an explicit, temporary operational decision.

Configuration added by the review:

- `HEALTH_READINESS_CACHE_SECONDS=5`: per-worker readiness TTL; `0` disables it.
- `AXES_LOCKOUT_BY_USERNAME=false`: optional account lockout with deliberate-lockout risk.
- `SESSION_COOKIE_SAMESITE=Lax` and `CSRF_COOKIE_SAMESITE=Lax`: use `None` only for a cross-site
  browser client over HTTPS.

## Deployment behavior

The image runs as UID/GID 10001. Static files are fingerprinted at build time. `fly deploy`
runs `migrate --noinput` once in a release Machine; a non-zero exit aborts the release. Web
readiness requires both PostgreSQL and Redis. Web and worker process groups use the same image
but scale independently.
Gunicorn workers recycle after about 1,000 requests with a jitter of 100.

Prefer backward-compatible expand/migrate/contract database changes:

1. Add nullable/new structures and deploy compatible code.
2. Backfill asynchronously in bounded, idempotent batches.
3. Switch reads/writes after metrics verify completion.
4. Enforce constraints or remove old structures in a later deploy.

Never combine a destructive migration with code that assumes it has already completed.

## Sentry

The SDK removes user context, bodies, query strings, cookies, credential headers, and common
secret extras. Health checks are not traced. Also enable Sentry's server-side default scrubbers,
configure low event retention, restrict project membership, and create alerts for:

- new/high-frequency errors;
- error-rate or p95 latency regression;
- failed Celery tasks and queue age;
- release regression after deploy.

Set `SENTRY_RELEASE` to a Git commit/image identifier in CI when a formal release pipeline is
added. Do not provide a Sentry auth token to runtime Machines.

## Verification and rollback

After deploy:

```text
fly checks list
fly status
fly logs
fly ssh console -C "python manage.py check --deploy"
```

Verify login/CSRF, tenant isolation, privacy request creation, one Celery task, object upload via
signed URL, and a deliberately captured non-sensitive Sentry test error. Inspect the Sentry
event to confirm no body, cookies, email, IP, or tokens arrived.

Application rollback does not reverse migrations. Roll back code only when the schema change is
backward-compatible. For data loss/corruption, stop writes, preserve evidence, restore Managed
Postgres to a new cluster, validate privately, attach the restored cluster, and document every
decision.
