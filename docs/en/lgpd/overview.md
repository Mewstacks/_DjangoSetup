# LGPD (Brazilian data protection) overview

> Engineering documentation, not legal advice. Deadlines, legal bases and the content of notices
> are settings and data you must confirm with your DPO or counsel. Items marked **to validate**
> are interpretations, not facts.

## What is built in

| Duty | Where |
|---|---|
| Know what you hold (art. 37, RoPA) | `<app>/privacy.py` classifies **every** model; a test fails until you do, another when a personal-looking field is not listed. `manage.py privacy_ropa` exports the register of processing; [catalog](../reference/data-catalog.md) |
| Purposes and lawful bases (arts. 6-7) | `ProcessingPurpose` with lawful basis, data categories, retention days and the consequence of refusing; seeded by `manage.py privacy_seed` |
| Consent (art. 8) | `ConsentRecord`: HMAC-chained per person, frozen notice and purpose digests, evidence (IP hash, UA hash). **Withdrawal is always possible** and is never rate limited. Cookie choices of visitors without an account are recorded as proof (`POST /api/v1/privacy/cookies/consent/`) |
| Transparency (arts. 9, 41) | Public endpoints: active notice, controller and DPO (`DPO_*`, `PRIVACY_CONTROLLER_*`, **required in production**), purposes, sub-processors and transfers, cookie categories. Texts in Portuguese by default (`PRIVACY_MAIL_LANGUAGE`) |
| Data subject rights (art. 18) | `DataSubjectRequest` for the 11 request types, intake for people without an account (e-mail verification), state machine with guarded transitions, SLA reminders; confirmation says whether data is held |
| Erasure, anonymization, blocking, export | Executors driven by the catalog; export is a sealed package behind an expiring, limited-use link; stored files leave the bucket with their rows |
| Retention (arts. 15-16) | `manage.py retention_sweep [--dry-run]` covers models with a `retention_field`, including uploads, API keys, cookie consents and **dormant accounts** (anonymized after the purpose's retention without sign-in; staff and people under a legal hold are never swept) |
| Incidents (art. 48) | `PersonalDataIncident`: ANPD deadline in business days (`PRIVACY_INCIDENT_BUSINESS_DAYS`, `PRIVACY_HOLIDAYS`, doubled by `PRIVACY_SMALL_AGENT`), the same period for the people affected, a 20-business-day window to complete a communication, reminders, `privacy_incident_export` |
| Impact assessment (art. 38) | `ImpactAssessment` model and a [template](templates.md) |
| Security (art. 46) | See [hardening](../security/hardening.md): encryption at rest for sensitive fields, keyed audit chain, MFA, strict production validators |
| Children (art. 14) and the ECA Digital | See below |
| Sub-processors and transfers (art. 33) | `SubProcessor` with country and transfer mechanism; `privacy_seed` creates **inactive** stubs for the platform's own vendors (Sentry, object storage, mail, Temporal, hosting) that you activate and complete |

## Children and the ECA Digital

LGPD art. 14 requires a parent's or guardian's specific consent for a child's data. The ECA Digital
(Lei 15.211/2025, in force since 17 March 2026; a regulating decree followed, as reported: check the primary text) goes further for
products likely to be used by minors: reliable, auditable age assurance (self-declaration does not
qualify), privacy by design and by default, and an impact assessment. **Whether it applies to your
product, and which method is adequate, is a legal question, and the ANPD's guidance is still
developing: confirm with counsel.**

What the platform gives you: the `child` data category (fields must be encrypted), purposes that
`involves_children` and demand `guardian_confirmed` on consent, and a seam for age assurance:
`AGE_ASSURANCE_BACKEND` names a class with `assess(user) -> AgeAssurance`
(`apps/privacy/age.py`). A consent grant from a person the backend reports as a minor is refused
without guardian confirmation. The default backend admits it cannot tell and changes nothing; a
product aimed at minors must replace it. Keep the decision (`is_minor`, how it was reached), never
the document.

## Requests

`access`, `confirmation`, `correction`, `anonymization`, `blocking`, `deletion`, `portability`,
`consent_withdrawal`, `sharing_information`, `automated_review`, `opposition`.

Status path: `received → verifying → in_progress → (legal_review) → completed | denied | cancelled`.
No other transition exists; illegal ones raise. The target response time is
`PRIVACY_REQUEST_TARGET_DAYS` (15) - **to validate** against the regulation in force. Correction,
opposition and automated-decision review go to `legal_review`: a person decides. **Destructive**
types (deletion, anonymization, blocking) require the requester to confirm by a mailed link before
anything is executed.

## Who is the controller

For your customers' account and billing data you are the controller; for what their members put
in the product you are usually the operator and the customer the controller. See
[ADR 17](../adr/controller-and-operator.md) and the
[data processing agreement template](templates.md): settle this with counsel before the first
customer.

## Running it

DSAR processing is a flow (Temporal workflow, or the local engine), with reminders at D-5 and
D-1 and an overdue state. Jobs: `privacy.dsar_sweep`, `privacy.dsar_sla`,
`privacy.incident_deadlines`, `privacy.retention_sweep`, `privacy.exports_cleanup`.

## Setup checklist

1. Set `PRIVACY_CONTROLLER_NAME`, `PRIVACY_CONTROLLER_ID` (CNPJ), `DPO_NAME`, `DPO_EMAIL`,
   `DPO_CONTACT_URL` (production refuses to start without a controller and a DPO channel).
2. `python manage.py privacy_seed` and review each purpose (basis, retention, consequence of
   refusing) with counsel; activate the sub-processors you use.
3. Publish a `PrivacyNotice` (immutable once active; publish a new version to change it) built from
   the [templates](templates.md).
4. List holidays in `PRIVACY_HOLIDAYS` for the deadline arithmetic.
5. Register your own models in `<app>/privacy.py` and rerun `scripts/gen_docs.py`.
6. `python manage.py doctor` reports what is still missing; review the
   [compliance matrix](compliance-matrix.md) for what the platform does not cover.
