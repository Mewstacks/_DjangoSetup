# ADR 13: The audit trail is keyed, and only an owner can prune it

**Status:** accepted. Replaces the unkeyed chain described in decision 8.

## Context

The trail is hash-chained per organization and guarded by a PostgreSQL trigger. A review found
three ways that was weaker than the documentation claimed:

1. The hash was plain SHA-256, so anyone able to write the table could rewrite history and recompute
   every hash consistently.
2. The trigger allowed a `DELETE` after `SET LOCAL app.audit_maintenance = 'on'`, which *any*
   session can run, so a compromised application account could erase the trail.
3. A chain proves what *precedes* its head. Deleting the newest events leaves a shorter chain that
   still verifies.

## Decision

- **Keyed chain.** Each hash is an HMAC under `AUDIT_HMAC_KEY` (environment, never the database).
  A database writer cannot re-chain without it. The same helper keys the consent chain.
- **Owner-only prune.** The trigger allows a delete only for the role that owns the table, and the
  only sanctioned delete is `audit_prune(chain, up_to_seq)`, a `SECURITY DEFINER` function whose
  `EXECUTE` is granted to the runtime role named in `AUDIT_RUNTIME_ROLE`. The runtime role has
  `INSERT` and `SELECT` on the table and nothing else (its `UPDATE`, `DELETE`, `TRUNCATE` are revoked
  by the migration). `doctor` warns when the runtime owns the table.
- **No row outside the chain.** A `CHECK (seq IS NOT NULL AND hash <> '')` refuses forged inserts
  (added `NOT VALID`, so rows from before chaining do not block it).
- **Heads leave the database.** The daily `maintenance.verify_audit` job logs each chain's head;
  `audit_verify --expect heads.json` compares a recorded head with the chain and catches tail
  removal.

## Consequences

- True only with two database roles (schema owner for migrations, runtime for the app). The Compose
  and Kubernetes manifests create them; a single-role deployment still gets the keyed chain, loses
  the privilege separation, and `doctor` says so.
- A superuser who also holds `AUDIT_HMAC_KEY` can still rewrite history. Ship the head lines to a
  system the database cannot reach (a log service with write-once storage) to detect that too.
- Rotating `AUDIT_HMAC_KEY` invalidates verification of older rows: start a new epoch, export the
  old chain first. No tooling for that yet; it is a deliberate non-goal until a customer needs it.
