# Hardening and key management

## Production refuses to start when

- the secret key or HMAC key is a placeholder, short or low-entropy, or two secrets are equal;
- the field-encryption key ring is malformed or lacks the active key;
- the database is not reached over TLS (or `DB_ALLOW_INSECURE_TRANSPORT` is not set deliberately);
- Redis has no auth/TLS (or `REDIS_ALLOW_INSECURE` is not set);
- hosts are wildcard or origins are not https; no proxy is declared (`TRUSTED_PROXY_IPS`,
  `TRUSTED_PROXY_COUNT` or `TRUSTED_PROXY_DIRECT`); a proxy entry is not a CIDR;
- the admin is enabled without `ADMIN_ALLOWED_IPS`; `NETGUARD_ALLOW_PRIVATE` is on; `LOG_LEVEL=DEBUG`.

## Always on

HTTPS redirect (health probes exempt), HSTS, secure/HTTP-only/SameSite cookies, CSP (default
`'self'`), `X-Frame-Options: DENY`, no-store on API responses, ASGI body-size limit, trusted-proxy
client-IP resolution, 12-character password minimum with common-password check.

## Key rotation

```bash
python scripts/generate_production_secrets.py --key-id v2 --existing-ring '{"v1":"..."}'
# set FIELD_ENCRYPTION_ACTIVE_KEY_ID=v2 and the new ring, deploy
python manage.py reencrypt_fields          # re-encrypts every encrypted column
# after it reports zero remaining on v1, remove v1 from the ring
```

Never regenerate the ring without `--existing-ring`: existing ciphertext would be unreadable.
`DJANGO_SECRET_KEY` rotation logs everyone out; `PRIVACY_HMAC_KEY` rotation breaks lookups of
hashed evidence, so rotate it only with a migration plan.

## Rotating other credentials

API keys: `rotate` (24 h overlap). Webhook secrets: `rotate-secret` (both signatures sent during
overlap). OAuth clients: revoke tokens, issue a new client. Database/Redis passwords: rotate in
the platform, update the secret, roll the pods; `readiness` goes unready until connected.
