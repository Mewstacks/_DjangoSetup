# LGPD (Brazilian data protection) overview

> Engineering documentation, not legal advice. Deadlines, legal bases and the content of notices
> are settings and data you must confirm with your DPO or counsel. Items marked **to validate**
> are interpretations, not facts.

## What is built in

| Duty | Where |
|---|---|
| Know what you hold (art. 37, RoPA) | `<app>/privacy.py` classifies **every** model; a test fails until you do. `manage.py privacy_ropa` exports the register of processing; [catalog](../reference/data-catalog.md) |
| Purposes and lawful bases (arts. 6-7) | `ProcessingPurpose` with lawful basis, data categories, retention days; seeded by `manage.py privacy_seed` |
| Consent (art. 8) | `ConsentRecord`: hash-chained per person, frozen notice and purpose digests, evidence (IP hash, UA hash). **Withdrawal is always possible** and is never rate limited |
| Transparency (arts. 9, 41) | Public endpoints: active notice, controller and DPO (`DPO_*`, `PRIVACY_CONTROLLER_*`), purposes, sub-processors and transfers, cookie categories |
| Data subject rights (art. 18) | `DataSubjectRequest` for the 11 request types, intake for people without an account (e-mail verification), state machine with guarded transitions, SLA reminders |
| Erasure, anonymization, blocking, export | Executors driven by the catalog; export is a sealed package behind an expiring link (`PRIVACY_EXPORT_TTL_DAYS`) |
| Retention (arts. 15-16) | `manage.py retention_sweep [--dry-run]`; `LegalHold` freezes a person's rows |
| Incidents (art. 48) | `PersonalDataIncident` with the ANPD notice deadline in business days (`PRIVACY_INCIDENT_BUSINESS_DAYS`, `PRIVACY_HOLIDAYS`) and reminders |
| Security (art. 46) | See [hardening](../security/hardening.md): encryption at rest for sensitive fields, audit chain, MFA, strict production validators |
| Children (art. 14) | Category `child` in the catalog marks fields for specific handling; consent evidence supports guardian records |

## Requests

`access`, `confirmation`, `correction`, `anonymization`, `blocking`, `deletion`, `portability`,
`consent_withdrawal`, `sharing_information`, `automated_review`, `opposition`.

Status path: `received → verifying → in_progress → (legal_review) → completed | denied | cancelled`.
No other transition exists; illegal ones raise. The target response time is
`PRIVACY_REQUEST_TARGET_DAYS` (15) - **to validate** against the regulation in force.
**Destructive** types (deletion, anonymization, blocking) require the requester to confirm by a
mailed link before anything is executed.

## Running it

DSAR processing is a flow (Temporal workflow, or the local engine), with reminders at D-5 and
D-1 and an overdue state. Jobs: `privacy.dsar_sweep`, `privacy.dsar_sla`,
`privacy.incident_deadlines`, `privacy.retention_sweep`.

## Setup checklist

1. Set `PRIVACY_CONTROLLER_NAME`, `PRIVACY_CONTROLLER_ID` (CNPJ), `DPO_NAME`, `DPO_EMAIL`,
   `DPO_CONTACT_URL`.
2. `python manage.py privacy_seed` and review each purpose (basis, retention) with counsel.
3. Publish a `PrivacyNotice` (immutable once active; publish a new version to change it).
4. List holidays in `PRIVACY_HOLIDAYS` for the deadline arithmetic.
5. Register your own models in `<app>/privacy.py` and rerun `scripts/gen_docs.py`.
6. Review the [compliance matrix](compliance-matrix.md) for what the platform does not cover.
