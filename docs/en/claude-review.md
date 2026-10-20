# Changes incorporated after the Claude review

[Versão em português](../pt-BR/revisao-claude.md)

This page records the code changes found after the external review. It describes current
behavior and the trade-offs that must be understood before deployment.

## Authentication and abuse protection

- Login now passes the original `HttpRequest` to django-axes. This lets middleware observe the
  lockout state and return `429` with `Retry-After` instead of silently falling back to `401`.
- `axes_username` normalizes addresses received under either `email` or `username`. Failures are
  associated with the attacked account rather than an empty username.
- `AXES_LOCKOUT_BY_USERNAME=false` is configurable. Enabling it also locks by account and
  mitigates brute force distributed across many IPs. The trade-off is deliberate third-party
  account lockout, so enabling it must be a deployment risk decision.
- Anonymous and login throttles use a backend-validated IP. A caller-controlled
  `X-Forwarded-For` cannot mint new buckets. On Fly.io, `Fly-Client-IP` is trusted only when
  `FLY_APP_NAME` exists; elsewhere the code uses `REMOTE_ADDR`.
- Authenticated throttles remain primarily user-based as defined by DRF, while every IP fallback
  uses the validated identifier.

## Encryption

`EncryptedTextField` now uses the model and column name as AES-256-GCM Associated Authenticated
Data (AAD). Ciphertext copied to a different column fails authentication instead of decrypting.

Limits and migration:

- Binding is per column, not per row; someone with direct database write access can still swap
  ciphertexts between records in the same column.
- Ciphertexts created by the previous field implementation have no AAD and will not decrypt
  automatically with the new implementation.
- If real data already exists, design and test a gradual migration that reads the legacy format
  and rewrites it with the new AAD before the final rollout. Keep old keys until old records and
  backups have expired.

## Performance and availability

- Organization listing uses a subquery and annotation for the current user's role. It no longer
  loads every member or requires an unnecessary `distinct()`.
- A test ensures listing query count does not grow with membership count.
- The public readiness check caches its result in each worker for
  `HEALTH_READINESS_CACHE_SECONDS` (default `5`). This reduces database queries and Redis writes
  without adding a throttle that itself depends on Redis. Set `0` to disable memoization.
- Audit events still validate fields and metadata but skip ORM uniqueness/constraint queries on
  the authentication hot path. UUIDs are application-generated and database constraints remain
  enforced.
- Gunicorn recycles workers after about 1,000 requests with a jitter of 100, limiting long-term
  memory growth and avoiding synchronized restarts.

## Cross-site cookies

`SESSION_COOKIE_SAMESITE` and `CSRF_COOKIE_SAMESITE` are configurable. The default remains
`Lax`. Use `None` only for a browser client on another site and always with HTTPS/Secure
cookies. Production rejects values other than `Lax`, `Strict`, or `None`.

Server-to-server Python clients do not depend on CORS or SameSite, but still use session and
CSRF for these authentication endpoints.

## Added tests

- Real lockout after repeated failures and a `429` response.
- Account-scoped lockout.
- Username normalization for django-axes.
- Protection against forging throttle buckets with `X-Forwarded-For`.
- Underlying DRF request IP handling and safe invalid-IP fallback.
- Rejection of ciphertext moved between columns.
- Current role on organization create/list and bounded query count.

Before release, run the full test suite, mypy, Ruff, `check --deploy`, and encrypted-data
compatibility tests in staging.
