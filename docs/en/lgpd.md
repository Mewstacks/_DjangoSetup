# LGPD implementation guide

[Versão em português](../pt-BR/lgpd.md)

The code supports accountability evidence; the controller still owns the legal decisions.
Before launch, appoint the responsible people and review this implementation with privacy/legal
counsel familiar with the product.

## Product data inventory

For every personal-data flow, record:

- controller/operator roles and processors;
- purpose and lawful basis—consent is not a universal default;
- data subjects and categories, source, recipients, and international transfers;
- minimum fields, retention trigger/period, erasure or anonymization behavior;
- security controls, high-risk assessment, and whether a RIPD is necessary.

Represent active purposes in `ProcessingPurpose`; publish a versioned notice with a SHA-256
checksum; only create `ConsentRecord` entries for consent-based purposes. Consent entries are
append-only decisions, so withdrawal does not erase evidence of the earlier grant.

## Rights workflow

Authenticated users can create and track requests without placing their personal details in
logs. Operations staff must verify identity proportionately, avoid collecting unnecessary
identity documents, route the request to product-specific data owners, and record the outcome.

The default operational target is 15 calendar days for a complete access response. The LGPD
also expects immediate action/response where possible, and deadlines differ by right and
context; do not treat the default as universal legal advice. Every product app must implement
explicit export, correction, blocking, portability, and erasure handlers. Erasure must account
for legal retention, fraud/security evidence, backups, processor copies, and anonymization.

## Retention

- Set a retention period for each purpose; zero or "forever" is not an acceptable unexplained
  default.
- Product-specific scheduled jobs should select eligible records in bounded batches, support
  dry-run metrics, and produce aggregate audit evidence without copying PII into task arguments.
- Keep legal holds explicit, approved, time-bound, and reviewable.
- Personal-data incident records have a five-year minimum retention guard.

## Incidents

Use `PersonalDataIncident` and the incident runbook. Confirm whether personal data was involved,
assess relevant risk/harm, preserve evidence, and have the controller/DPO determine
notification. ANPD Resolution CD/ANPD 15/2024 generally requires notifying the ANPD and affected
subjects within three business days when a confirmed incident involving personal data may cause
relevant risk or harm. Do not calculate Brazilian holidays in application code without an
approved legal calendar; staff set and verify the deadline.

## Vendors and international transfers

Complete due diligence and appropriate data-processing/international-transfer terms for Fly.io,
Managed Postgres, Upstash, Tigris, Sentry, email, payments, and every product vendor. Tigris is
globally distributed, so do not assume Brazil-only object residency. If the product requires
strict regional residency, use a private S3-compatible store in a Brazilian region and update
the data map and contracts.

## Evidence to retain

Keep approved versions of the privacy notice, processing inventory, legitimate-interest/RIPD
assessments where applicable, processor contracts, access reviews, training, restore tests,
key-rotation records, vulnerability remediation, subject-request outcomes, and incident
decisions. Keep evidence in a controlled compliance repository, not only in the application DB.

Official references:

- [LGPD consolidated text](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [ANPD data-subject rights](https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares)
- [ANPD security incident guidance](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis)
