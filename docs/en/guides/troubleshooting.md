# Troubleshooting

Production settings refuse to start on unsafe or missing configuration, and say which variable to
fix. This page maps each refusal to its cause.

## The minimum production environment

| Variable | Why |
|---|---|
| `DJANGO_SECRET_KEY`, `PRIVACY_HMAC_KEY`, `AUDIT_HMAC_KEY` | Three different random secrets: `python scripts/generate_production_secrets.py` |
| `FIELD_ENCRYPTION_ACTIVE_KEY_ID`, `FIELD_ENCRYPTION_KEYS` | The key ring (same script) |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_CORS_ALLOWED_ORIGINS` | Your hosts; origins are `https://` |
| `PUBLIC_URL` | `https://app.example.com`: base of every link we e-mail |
| `DATABASE_URL` or `DB_*` | PostgreSQL, TLS with certificate checking (`sslmode=verify-full`) |
| `REDIS_URL` | `rediss://`; carries sessions, lockout and throttles |
| `TRUSTED_PROXY_COUNT` or `TRUSTED_PROXY_IPS` | How the app is reached; without it every client looks like the proxy |
| `S3_BUCKET` | Uploads and exports (or `OBJECT_STORAGE_REQUIRED=false` with a persistent volume) |
| `SENTRY_DSN` or `SENTRY_ENABLED=false` | Error reporting, or an explicit no |
| `EMAIL_HOST` ... | A real mail backend |
| `PRIVACY_CONTROLLER_NAME`, `DPO_EMAIL` or `DPO_CONTACT_URL` | Who is responsible and the channel to them |

## "ImproperlyConfigured: ..." at start-up

| Message begins | Cause and fix |
|---|---|
| `... looks like a placeholder` / `has too little variety` | A secret copied from an example. Generate real ones |
| `... must differ from ...` | Two secrets are equal |
| `Production database must use TLS` / `sslmode=require ... never checks` | Use `sslmode=verify-full`; on a private network you control set `DB_ALLOW_INSECURE_TRANSPORT=true` (or `DB_ALLOW_UNVERIFIED_TLS=true` to keep `require`) |
| `REDIS_URL must use rediss://` | Use TLS, or `REDIS_ALLOW_INSECURE=true` on a private network |
| `Declare how the app is reached` | Set `TRUSTED_PROXY_COUNT`/`TRUSTED_PROXY_IPS`, or `TRUSTED_PROXY_DIRECT=true` |
| `Production object storage is required` | Set `S3_BUCKET` |
| `SENTRY_DSN is required` | Give a DSN or `SENTRY_ENABLED=false` |
| `PUBLIC_URL must be the https origin` | `https://host`, no path |
| `Set PRIVACY_CONTROLLER_NAME` / `Set DPO_EMAIL or DPO_CONTACT_URL` | Publish who answers for personal data |
| `Production Temporal needs sealed payloads` / `must use TLS` | Keep `TEMPORAL_PAYLOAD_ENCRYPTION=true`; TLS or an API key, or `TEMPORAL_ALLOW_INSECURE=true` on a private network |
| `ADMIN_ENABLED in production requires ADMIN_ALLOWED_IPS` | Name the networks that may reach `/admin/` |

## Symptoms

| You see | Look at |
|---|---|
| Sign-in works but `/admin/` answers 403 `mfa_required` | Staff need an authenticator first (`/accounts/2fa/`) |
| `403 mfa_required` or "must enable two-factor" on organization endpoints | `ORG_PRIVILEGED_MFA_REQUIRED` in production: enrol an authenticator |
| `403 reauthentication_required` creating a key | Sign in again; the window is `APIKEY_REQUIRE_RECENT_AUTH_SECONDS` |
| Every user shares one rate limit or lockout | The proxy is not declared correctly (`doctor` -> client ip) |
| `429` from `/mcp` | `MCP_RATE_PER_MINUTE_IP`; many agents behind one address |
| Webhook endpoint refused with `blocked_address` | The URL resolves to a non-public address (the SSRF guard) |
| Uploads fail with `scanner_unavailable` | `UPLOAD_CLAMAV_ADDR` is set and unreachable; fix it or set `UPLOAD_CLAMAV_REQUIRED=false` knowingly |
| `audit_verify` reports a break | See the audit runbook in [Runbooks](../deploy/runbooks.md) |
| `doctor` warns "the runtime role can rewrite the audit trail" | Connect as a role that does not own the schema ([Hardening](../security/hardening.md)) |
| OAuth client cannot register | `OAUTH_DCR_ANONYMOUS`, or its redirect URI is neither `https` nor loopback |
| The image says OpenTelemetry is missing | Build with `--build-arg EXTRAS="--extra otel"` |

Anything else: `python manage.py doctor --strict`, then the logs (JSON, one line per event,
carrying `request_id`).
