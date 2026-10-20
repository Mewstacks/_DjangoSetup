# Stack learning path

[Versão em português](../pt-BR/trilha-aprendizado.md) ·
[Back to the summary](technologies-and-middleware.md)

Read in the order that fits your work. Each guide explains the technology's importance, real use,
security value, and limits.

## 1. Fundamentals

| Subject | Technologies | Guide |
| --- | --- | --- |
| Backend and APIs | HTTP, JSON, Python, Django, and DRF | [API, Django, and DRF](fundamentals/api-django-drf.md) |
| Shared SaaS | Organization, Membership, and scoping | [Tenants and isolation](fundamentals/tenants-and-isolation.md) |
| HTTP pipeline | Middleware, CORS, CSRF, CSP, and Axes | [Middleware and security](fundamentals/middleware-and-security.md) |

## 2. Data and processing

| Subject | Technologies | Guide |
| --- | --- | --- |
| Main database | PostgreSQL, psycopg, ORM, and migrations | [PostgreSQL, ORM, and migrations](technologies/postgresql-orm-migrations.md) |
| Temporary data | Redis, cache, sessions, and rate limits | [Redis, cache, and sessions](technologies/redis-cache-sessions.md) |
| Asynchronous work | Celery, broker, worker, and idempotency | [Celery and jobs](technologies/celery-jobs.md) |
| Files | Tigris/S3, django-storages, and signed URLs | [Object storage](technologies/object-storage.md) |

## 3. Security and privacy

| Subject | Technologies | Guide |
| --- | --- | --- |
| Data protection | Argon2, AES-GCM, HMAC, and key management | [Encryption, passwords, and secrets](technologies/encryption-passwords-secrets.md) |
| Technical controls | Cookies, headers, throttling, and audit | [Security model](security.md) |
| Privacy program | LGPD, retention, and rights | [LGPD guide](lgpd.md) |

## 4. Runtime and deployment

| Subject | Technologies | Guide |
| --- | --- | --- |
| Server and hosting | ASGI, Gunicorn, Uvicorn, Docker, and Fly.io | [Runtime, Docker, and Fly](technologies/runtime-docker-fly.md) |
| Operations | Sentry, JSON logs, request IDs, and health checks | [Sentry, logs, and health checks](technologies/sentry-logs-health.md) |

## 5. Contract and quality

| Subject | Technologies | Guide |
| --- | --- | --- |
| API contract | OpenAPI, drf-spectacular, and Swagger | [OpenAPI and Swagger](technologies/openapi-swagger.md) |
| Quality | pytest, coverage, Ruff, mypy, pip-audit, and CI | [Tests, quality, and CI](technologies/tests-quality-ci.md) |

## Recommended order

To build endpoints, read fundamentals → PostgreSQL → tenants → tests. To deploy, read runtime →
Redis → Celery → observability. Before real data, read security → encryption → LGPD → runbooks.

You do not need to master everything before starting. Learn one layer, use it in a small example,
and write a test before moving on.
