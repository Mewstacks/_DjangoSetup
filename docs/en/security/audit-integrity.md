# Audit integrity

Each organization (plus one system chain) has its own hash chain. A row stores an **HMAC** of the
previous hash and its canonical content, keyed by `AUDIT_HMAC_KEY` (held in the environment, not
the database); inserts take a PostgreSQL advisory lock as their last statement so chains stay linear
under concurrency. The consent history is chained the same way.

- Foreign keys to actors and organizations are plain ids (no constraint): deleting a user or an
  organization never touches the trail.
- A trigger rejects `UPDATE`, `DELETE` and `TRUNCATE`. The only sanctioned delete is the
  `audit_prune()` function used by retention, and the trigger honours it only for the role that owns
  the table. The runtime role holds `INSERT` and `SELECT` on the table and `EXECUTE` on the function
  (`AUDIT_RUNTIME_ROLE`); it cannot update, delete, truncate or disable anything.
  Pruning writes an **anchor** row that keeps the chain verifiable after old rows go
  (`AUDIT_RETENTION_DAYS`, default 365, 0 = keep forever).
- A `CHECK` constraint refuses a row without `seq` or `hash`, so a forged insert cannot sit outside
  the chain.
- Metadata is validated by key fragment and scanned with the redaction patterns; personal data does
  not belong in the trail. Failed sign-ins are coalesced per account and capped per client address;
  refused actions are capped per credential, so a caller cannot choose how fast the table grows.
- `python manage.py audit_verify [--org ID]` recomputes chains and exits non-zero on a break. The
  daily job `maintenance.verify_audit` does the same and logs each chain's head (`audit_head`).

## The newest rows

A chain proves what precedes its head: deleting the newest events leaves a shorter chain that still
verifies. Record the heads where the database cannot reach and check against them:

```bash
python manage.py audit_verify --json > heads.json      # or collect the audit_head log lines
python manage.py audit_verify --expect heads.json      # fails with "newest events are missing"
```

## What it does not defend against

The table owner or a database superuser who also holds `AUDIT_HMAC_KEY`. Separate the database
roles ([Deploy](../deploy/overview.md#two-database-identities)), keep the key in a secret manager
the database host cannot read, and ship head lines to write-once storage. `manage.py doctor` warns
when the runtime role owns the table or can modify it.

A broken chain means rows were changed outside the application. Treat it as an incident: see the
[runbooks](../deploy/runbooks.md).
