# Redis, cache, and sessions

[Versão em português](../../pt-BR/tecnologias/redis-cache-sessoes.md) ·
[Back to the learning path](../learning-path.md)

## What is Redis?

Redis is very fast storage, usually memory-based. It is best for temporary or rebuildable data,
not the only copy of an important record.

This project uses it for:

- cache;
- accelerated sessions;
- DRF throttle and django-axes counters;
- Celery broker and results.

## Cache

Cache temporarily stores an expensive result:

```text
First read → PostgreSQL → store in Redis
Next read → Redis → faster response
```

Define expiration and invalidation. Stale cache can show incorrect or cross-tenant data. Include
the organization ID in keys and avoid caching sensitive data unnecessarily.

## Sessions

The backend uses `cached_db`: PostgreSQL persists sessions and Redis accelerates reads. The browser
stores only an identifier in a cookie, not the entire session.

`HttpOnly`, `Secure`, and `SameSite` cookies reduce risk, but a stolen session remains dangerous.

## Rate limits and login

DRF stores throttle counters in cache; Axes stores login failures. Shared Redis lets every Machine
see the same counters. Local cache would give an attacker a fresh limit on every instance.

## Failure and scale

`IGNORE_EXCEPTIONS=False` exposes failure instead of pretending cache worked. Readiness fails when
Redis is unavailable, avoiding silent loss of security controls.

Use a different `CACHE_KEY_PREFIX` per product and environment. Monitor memory, latency,
connections, evictions, and broker persistence.

Ask: “if this disappears now, can it be rebuilt?” If not, it probably belongs in PostgreSQL.
