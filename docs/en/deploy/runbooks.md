# Runbooks

## Backup and restore

- Logical backup: compose `--profile backup` or the Kubernetes CronJob writes
  `pg_dump --format=custom` nightly and keeps 14 days. Copy dumps off the machine as well.
- Restore into an empty database: `pg_restore --clean --if-exists --no-owner -d "$DB" file.dump`,
  then `entrypoint migrate`, then `entrypoint manage audit_verify --all`.
- Keep the **encryption key ring** with the backups' recovery material, stored apart from them:
  without it encrypted columns are unreadable.
- Practise a restore at least quarterly; the goal is a timed, written procedure.

## Personal data incident

1. Create the incident (admin or API): discovery time, categories, estimated subjects.
2. The ANPD notice deadline is computed in business days (`PRIVACY_INCIDENT_BUSINESS_DAYS`,
   `PRIVACY_HOLIDAYS`); reminders fire hourly via `privacy.incident_deadlines`.
3. Contain: revoke API keys and OAuth tokens, rotate secrets ([hardening](../security/hardening.md)),
   disable affected webhook endpoints.
4. Preserve evidence: `audit_verify --all`, export audit rows for the window.
5. Decide notification of ANPD and subjects with the DPO and counsel (**3 business days is to
   validate**), then record the outcome and close.

## Audit chain broken

`audit_verify` exits non-zero: stop pruning, snapshot the database, find the first bad row,
compare with the latest backup, treat as a security incident.

## Temporal unavailable

`/api/v1/health/ready/` stays up (worker state is informational). Starts of Temporal-only flows
fail fast; portable flows keep working only if you set `TEMPORAL_ENABLED=false` and run the
`scheduler`. After recovery run `flows_sync`. Webhook deliveries retry on their own.

## A webhook endpoint is disabled

It reached `WEBHOOK_DISABLE_AFTER` consecutive failures. Fix the receiver, re-enable the endpoint,
then `redeliver` the failed deliveries.

## Upgrade

Read `CHANGELOG.md`; deploy order: migrate job, then web, then worker/scheduler. Migrations are
additive between minor releases. Roll back the image, not the database.
