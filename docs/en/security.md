# Security model

[Versão em português](../pt-BR/seguranca.md)

## Default controls

- HTTPS redirect, secure/HTTP-only/SameSite cookies, HSTS, strict hosts/origins, CSRF, XSS
  escaping, clickjacking protection, MIME sniffing protection, referrer policy, and CSP.
- Argon2 passwords, 12-character minimum, lockout after repeated failures, generic credential
  errors, and shared Redis-backed authentication throttles.
- django-axes normalizes the attacked account and receives the original request. IP throttles
  ignore caller-provided `X-Forwarded-For` and use only the backend-validated address.
- JSON-only production APIs, authenticated-by-default DRF permissions, bounded pagination and
  uploads, explicit CORS allowlists, and request IDs.
- Non-root immutable container, pinned direct dependencies, CI lint/tests/dependency audit,
  secret scanning, and a production image build.
- PII-safe logging and Sentry: request bodies, query strings, cookies, user context, and secret
  headers are removed before transmission.

## Rate limiting and lockout

Throttle buckets are keyed by `apps.common.network.client_ip`, which trusts only the direct peer
(`REMOTE_ADDR`) unless trusted proxies are configured — `TRUSTED_PROXY_IPS` (proxy CIDRs) or
`TRUSTED_PROXY_COUNT` (number of proxies in front). DRF's own `get_ident` reads the
caller-supplied `X-Forwarded-For` whenever `NUM_PROXIES` is unset, which lets a client mint a
fresh bucket per request, so `NUM_PROXIES` is pinned to `0` and every throttle derives from
`apps.common.throttling`. This is host-agnostic; set the two variables to match your edge (behind
one reverse proxy, `TRUSTED_PROXY_COUNT=1`).

Lockout is scoped to `(username, ip_address)`. Set `AXES_LOCKOUT_BY_USERNAME=true` to also lock
on the username alone, which stops a brute force spread over many addresses at the cost of
letting a third party lock somebody out on purpose.

`SESSION_COOKIE_SAMESITE` and `CSRF_COOKIE_SAMESITE` default to `Lax`, which assumes a same-site
browser client. A SPA served from a different site needs `None`, and production then requires
HTTPS-only cookies for it to be accepted at all.

## Encryption

Infrastructure encryption and application encryption solve different threats:

- Fly Managed Postgres protects transport and storage media.
- HTTPS protects browser/API transport.
- `EncryptedTextField` uses AES-256-GCM with a new 96-bit nonce per write and authenticates the
  ciphertext. The stored format contains a version and key ID for rotation.
- Model and column names are used as AAD, preventing silent ciphertext movement to another
  column.
- Each ciphertext is bound to its model and column as GCM associated data, so a value cannot be
  moved into another field and still decrypt. Row identity is deliberately not part of that
  binding, because the primary key is unavailable when Django hydrates a field from a query
  result: a same-column row swap by someone with database write access remains possible.
- Field keys and the HMAC key are independent from Django's signing key. Production refuses to
  boot without all of them.

Keep the active field key plus old decrypt-only keys in `FIELD_ENCRYPTION_KEYS`. Rotate by
adding a new ID, making it active, deploying, re-saving affected rows in bounded background
batches, verifying no old key IDs remain, then removing the old key in a later release. Never
remove a key before database backups that contain it have expired or been cryptographically
retired.

Column AAD changes the authenticated format: ciphertexts written by the previous implementation
must be read through a legacy path and rewritten by a tested migration. Binding does not include
the row ID, so it cannot prevent swaps between records in the same column.

Do not encrypt values just to claim that everything is encrypted. Randomized ciphertext cannot
be indexed or searched normally and can break uniqueness. Use infrastructure encryption for
ordinary indexed fields; use application encryption for especially confidential free text,
tokens, identifiers, and incident/request narratives.

## Authentication limitations

The included session authentication is the safest default for a same-site first-party web app.
It does not include customer signup, password reset email, MFA, enterprise SSO, or service API
keys because those flows require product decisions. Before exposing privileged staff access,
add WebAuthn/TOTP or an OIDC identity provider with mandatory MFA. Keep Django admin disabled
or access-controlled until that is complete.

`AXES_LOCKOUT_BY_USERNAME=true` mitigates distributed attacks against one account but also lets
a third party deliberately lock that account. Evaluate this trade-off before enabling it.

## Required production work

- Put the application behind a rate-limiting edge/WAF for volumetric and bot attacks.
- Restrict Fly organization membership, require MFA/SSO, rotate deploy tokens, and separate
  production from non-production organizations.
- Configure Sentry server-side scrubbers and least-retention settings in addition to SDK
  scrubbing.
- Patch dependencies promptly and subscribe to Django, Fly, PostgreSQL, Redis, and Sentry
  security advisories.
- Perform threat modeling, SAST/DAST, restore tests, and an independent penetration test before
  high-risk or large-scale processing.

See [the incident runbook](runbooks/incident-response.md) and
[backup/restore runbook](runbooks/backup-restore.md).
