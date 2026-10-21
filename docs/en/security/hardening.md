# Hardening and key management

## Production refuses to start when

- the secret key, the privacy HMAC key or the audit HMAC key is a placeholder, short or low-entropy,
  or two secrets are equal; a `DJANGO_SECRET_KEY_FALLBACKS` / `PRIVACY_HMAC_KEYS_PREVIOUS` entry is weak;
- the field-encryption key ring is malformed or lacks the active key;
- the database is not reached over TLS **with certificate checking** (`sslmode=verify-ca` or
  `verify-full`); `require` encrypts without checking who answered and needs the explicit
  `DB_ALLOW_UNVERIFIED_TLS`, an unencrypted link needs `DB_ALLOW_INSECURE_TRANSPORT`;
- Redis is not `rediss://` (a password over plaintext protects nothing against a listener) unless
  `REDIS_ALLOW_INSECURE` records the decision;
- hosts are wildcard or origins are not https; `PUBLIC_URL` is not an https origin; no proxy is
  declared (`TRUSTED_PROXY_IPS`, `TRUSTED_PROXY_COUNT` or `TRUSTED_PROXY_DIRECT`); a proxy entry is
  not a CIDR;
- Temporal is on without sealed payloads, or without TLS / an API key / `TEMPORAL_ALLOW_INSECURE`;
- no controller or DPO channel is declared (`PRIVACY_CONTROLLER_NAME`, `DPO_EMAIL` or
  `DPO_CONTACT_URL`);
- the admin is enabled without `ADMIN_ALLOWED_IPS`; `NETGUARD_ALLOW_PRIVATE` is on; `LOG_LEVEL=DEBUG`.

`python scripts/verify.py` runs `manage.py check --deploy --fail-level WARNING` with production
settings: a warning is a failure. The two HSTS opt-ins (subdomains, preload) are silenced until you
turn them on because they are commitments about the whole parent domain.

## Always on

HTTPS redirect (health probes exempt), HSTS, secure/HTTP-only/SameSite cookies, a `'self'`-only CSP
with a violation sink, `X-Frame-Options: DENY`, `Cross-Origin-Opener-Policy` and
`Cross-Origin-Resource-Policy` `same-origin`, `Permissions-Policy` (camera, microphone, location,
payment ... off), `nosniff`, a strict referrer policy, no-store on API responses, an ASGI body-size
limit and body-read timeout (408), trusted-proxy client-IP resolution, Argon2 password hashing,
12-character password minimum with common-password check, CORS limited to `/api/`.

## Account protection

Staff need an authenticator for the admin; owners and administrators for the organization endpoints
(production); creating or rotating an API key needs a recent sign-in; a password or second-factor
reset revokes the person's keys; non-superuser staff cannot touch superusers; OAuth tokens are
stored as checksums. See [accounts](../guides/auth.md).

## Outbound requests

Everything a user can point the server at (webhooks, OAuth client metadata) passes the network
guard: `https` only, **global** addresses only (an allow-list: carrier-grade NAT, the Alibaba and
cloud metadata addresses, IPv6 tunnel forms and NAT64 wrappers of private IPv4 are refused), the
validated address is the one connected to, no redirects, no proxy from the environment, a total
deadline, a size cap, and no decompression. The Kubernetes NetworkPolicy repeats this at the network
layer: egress to the public internet excludes every private range and the metadata endpoint.

## Database roles

The runtime connects as a role that owns nothing; migrations run as the owner. See
[Deploy](../deploy/overview.md#two-database-identities) and [Audit integrity](audit-integrity.md).

## Key rotation

```bash
python scripts/generate_production_secrets.py --key-id v2 --existing-ring '{"v1":"..."}'
# set FIELD_ENCRYPTION_ACTIVE_KEY_ID=v2 and the new ring, deploy
python manage.py reencrypt_fields          # re-encrypts every encrypted column and the MFA secrets
# after it reports zero unreadable rows, remove v1 from the ring
```

Never regenerate the ring without `--existing-ring`: existing ciphertext would be unreadable.

| Secret | Rotation |
|---|---|
| `DJANGO_SECRET_KEY` | Old value to `DJANGO_SECRET_KEY_FALLBACKS`; nobody is logged out; drop it after the session lifetime |
| `PRIVACY_HMAC_KEY` | Old value to `PRIVACY_HMAC_KEYS_PREVIOUS`; API keys and data subjects are rewritten under the new key on first use |
| `AUDIT_HMAC_KEY` | Starts a new epoch (older rows no longer verify under the new key): export the chain first |

## Rotating other credentials

API keys: `rotate` (24 h overlap). Webhook secrets: `rotate-secret` (both signatures sent during
overlap). OAuth clients: revoke tokens, issue a new client. Database/Redis passwords: rotate in
the platform, update the secret, roll the pods; `readiness` goes unready until connected.

## What this does not cover

A compromised host or build pipeline; a malicious superuser who also holds the keys (mitigated by
audit and the admin allow-list, not prevented); SSO/SCIM. See the [threat model](threat-model.md).
