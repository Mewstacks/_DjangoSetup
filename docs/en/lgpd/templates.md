# LGPD document templates

Starting points for the documents the LGPD asks you to have. **They are templates, not legal
advice.** The text depends on your processing, your contracts and your sector; have a lawyer with
LGPD experience adapt and approve each one before it is published or signed. Placeholders are
`{{like this}}`.

| Document | Template | Used with |
|---|---|---|
| Privacy notice (arts. 6, 9, 18) | [English](../../templates/privacy-policy.en.md) - [Português](../../templates/privacy-policy.pt-BR.md) | `PrivacyNotice`; the public transparency endpoint |
| Terms of service | [English](../../templates/terms-of-service.en.md) - [Português](../../templates/terms-of-service.pt-BR.md) | Sign-up flow |
| Data processing agreement (arts. 5, 39, 42) | [English](../../templates/data-processing-agreement.en.md) - [Português](../../templates/data-processing-agreement.pt-BR.md) | Customers for whom you are the operator |
| Impact assessment, RIPD (art. 38) | [English](../../templates/dpia-ripd.en.md) - [Português](../../templates/dpia-ripd.pt-BR.md) | `ImpactAssessment` model |

## Filling them from the platform

- **Controller and DPO**: `PRIVACY_CONTROLLER_NAME`, `PRIVACY_CONTROLLER_ID`, `DPO_NAME`,
  `DPO_EMAIL`, `DPO_CONTACT_URL` (also published by `GET /api/v1/privacy/transparency/`).
- **What you collect and why**: `python manage.py privacy_ropa` prints the register generated from
  the data catalog; the purposes, lawful bases and retention come from `ProcessingPurpose`.
- **Who else sees the data**: the active `SubProcessor` rows (name, country, transfer mechanism).
- **How long you keep it**: each purpose's `retention_days`, plus `AUDIT_RETENTION_DAYS`.
- **Rights and how to use them**: the public request endpoint and the 15-day response target.
- **Cookies**: the categories at `GET /api/v1/privacy/cookies/` and the consent record you keep.

## Publishing the notice

A published `PrivacyNotice` is immutable (consents point at its checksum). Put the document at a
stable URL, compute the SHA-256 of **the document**, create the notice with both, and activate it.
To change it, publish a new version.

## Review rhythm

Re-read the notice and the register when you add a purpose, a sub-processor, a country or a
category of data; at least once a year otherwise.
