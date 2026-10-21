# Runbooks

## Backup and restore

- Logical backup: compose `--profile backup` or the Kubernetes CronJob writes
  `pg_dump --format=custom` nightly (owner-only file mode) and keeps 14 days. Dumps hold **every
  tenant's data in the clear**: keep the volume encrypted and copy dumps off the machine encrypted.
- Restore into an empty database: `pg_restore --clean --if-exists --no-owner -d "$DB" file.dump`,
  then `entrypoint migrate` (as the schema owner, with `AUDIT_RUNTIME_ROLE` set), then
  `entrypoint manage audit_verify`.
- **Re-apply erasures after a restore.** A restore brings back people who were erased after the
  backup was taken, and the platform keeps no identity after an erasure. Keep a ledger **outside
  the database** (request id, date, and how to identify the person, under access control) of
  erasures made since the last backup, and repeat each one after a restore. Short backup retention
  shrinks the problem; say the retention in the privacy notice.
- Keep the **encryption key ring** and `AUDIT_HMAC_KEY` with the backups' recovery material, stored
  apart from them: without the ring encrypted columns are unreadable; without the audit key the
  chain cannot be verified.
- Practise a restore at least quarterly; the goal is a timed, written procedure.

## Personal data incident

1. Create the incident (admin or API): discovery time, categories, estimated subjects, measures.
2. The ANPD notice deadline is computed in business days (`PRIVACY_INCIDENT_BUSINESS_DAYS`,
   `PRIVACY_HOLIDAYS`, doubled by `PRIVACY_SMALL_AGENT`); the people affected have the same
   period; a first communication may be completed up to 20 business days after it. Reminders fire
   hourly via `privacy.incident_deadlines`.
3. Contain: revoke API keys and OAuth tokens, rotate secrets ([hardening](../security/hardening.md)),
   disable affected webhook endpoints.
4. Preserve evidence: `audit_verify`, export audit rows for the window.
5. Decide notification of the ANPD and the people affected with the DPO and counsel
   (**the clock starting at confirmation, 3 business days and who counts as a small agent are to
   validate**), assemble the content with `manage.py privacy_incident_export REF`, then record the
   outcome and close. Records are kept five years.

## Audit chain broken

`audit_verify` exits non-zero (or the daily job logs `audit_chain_broken`): stop pruning, snapshot
the database, find the first bad row, compare with the latest backup, treat as a security incident.
`newest events are missing` means the chain was cut at the end: compare with the head lines you
shipped. Also run `manage.py doctor`: if the runtime role can rewrite the trail, fix that first.

## Rotating secrets

| Secret | Procedure |
|---|---|
| `DJANGO_SECRET_KEY` | Move the old value to `DJANGO_SECRET_KEY_FALLBACKS`, set the new one, deploy; drop the old after `SESSION_COOKIE_AGE_SECONDS` |
| Field-encryption key | New id in the ring, switch the active id, `manage.py reencrypt_fields` (also reseals MFA secrets), drop the old key after it reports zero unreadable |
| `PRIVACY_HMAC_KEY` | Put the old value in `PRIVACY_HMAC_KEYS_PREVIOUS`, set the new one; API keys and data subjects are rewritten on first use; drop the old once keys have been used or reissued |
| `AUDIT_HMAC_KEY` | Not rotatable in place: start a new epoch (export the old chain, then new key) |
| Database / Redis password | Rotate in the platform, update the secret, roll the pods; `readiness` goes unready until connected |
| API keys, webhook secrets | `rotate` / `rotate-secret` (24 h overlap) |
| OAuth clients | Revoke tokens, issue a new client |

## Temporal unavailable

`/api/v1/health/ready/` stays up (worker state is informational). Starts of Temporal-only flows
fail fast; portable flows keep working only if you set `TEMPORAL_ENABLED=false` and run the
`scheduler`. After recovery run `flows_sync`. Webhook deliveries retry on their own.

## A webhook endpoint is disabled

It reached `WEBHOOK_DISABLE_AFTER` consecutive failures. Fix the receiver, re-enable the endpoint,
then `redeliver` the failed deliveries.

## Upgrade

Read `CHANGELOG.md`; deploy order: migrate job, then web, then worker/scheduler. Migrations are
additive between minor releases. Roll back the image, not the database. See
[Upgrading from upstream](../guides/upgrading.md).
