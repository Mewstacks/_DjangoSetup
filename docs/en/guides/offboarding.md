# Offboarding a tenant

A customer leaves, or asks for their data. Both are common; do them the same way every time.

## Give them their data

Two levels, in this order:

1. **What the platform exports for a person**: a data-subject access or portability request produces
   a sealed export of everything the catalog says it holds about that person, behind an expiring,
   limited-use link (`PRIVACY_EXPORT_TTL_DAYS`, `PRIVACY_EXPORT_MAX_DOWNLOADS`).
2. **What the organization owns** (its business data): export it with your own action, for example
   `invoices.export`, scoped to the organization and audited. The catalog tells you the models; the
   [data catalog](../reference/data-catalog.md) is the checklist. Hand it over through a link that
   expires, never as a mail attachment.

## Close the organization

1. Revoke access: set `Organization.is_active=False` (members and keys stop working on the next call),
   revoke API keys and OAuth tokens, disable webhook endpoints.
2. Wait out your contractual grace period; say how long in the terms.
3. Erase. Business data of the organization is **yours to delete** (it is the tenant's data, held for
   them); personal data of its members is handled per person through the erasure executors, which
   honour legal holds. Uploaded files leave the bucket with their rows.
4. Keep only what a legal duty requires (invoices, consent evidence, incident records, the audit
   trail until its retention ends) and say so in the privacy notice.
5. Record it: an audit event, and a note in the register of processing if the purpose changed.

## What deletion does not reach

- **Backups** keep the data until they expire. Say the backup retention in the notice, and after
  restoring a backup re-apply erasures made since (the runbook step).
- **The audit trail** points at ids, not content, and is pruned by `AUDIT_RETENTION_DAYS`.
- **Logs** are redacted at write time and age out with your log retention.

## Controller or operator

For their members' data in your product you are usually the **operator** and the customer the
**controller** (LGPD arts. 5 and 39): they instruct, you execute. For your own customers' account
and billing data you are the controller. Write which is which in the contract and the privacy
notice; a data-processing agreement template is in [LGPD templates](../lgpd/templates.md). This
split decides who answers a data subject, so settle it with counsel before the first customer.
