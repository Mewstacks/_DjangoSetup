# Audit integrity

Each organization (plus one system chain) has its own hash chain. A row stores
`hash = SHA-256(prev_hash || canonical row)`; inserts take a PostgreSQL advisory lock as their
last statement so chains stay linear under concurrency.

- Foreign keys to actors and organizations are plain ids (no constraint): deleting a user or an
  organization never touches the trail.
- A trigger rejects UPDATE and DELETE (and TRUNCATE) unless the transaction sets
  `app.audit_maintenance`, which only the prune job does; pruning writes an **anchor** row that
  keeps the chain verifiable after old rows go (`AUDIT_RETENTION_DAYS`, 0 = keep forever).
- Metadata is validated by key fragment and scanned with the redaction patterns; personal data
  does not belong in the trail.
- `python manage.py audit_verify [--all]` recomputes chains and exits non-zero on a break.
  Schedule it (a Temporal schedule, a CronJob, or CI against a restored backup).

A broken chain means rows were changed outside the application. Treat it as an incident: see the
[runbooks](../deploy/runbooks.md).
