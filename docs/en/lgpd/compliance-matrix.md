# LGPD compliance matrix

Article → platform feature → code → test. "Operator" means the organization running the system
must still do something. Interpretations are marked **to validate**.

| Art. | Requirement | Platform | Code | Test |
|---|---|---|---|---|
| 5, 39, 42 | Controller and operator | Guidance, DPA template; data model not split by role ([ADR 17](../adr/controller-and-operator.md)); operator: decide and write it down | - | - |
| 6 | Principles (purpose, necessity, security) | Purposes with retention; classification forces a decision per model | `privacy.models.ProcessingPurpose`, `privacy.catalog` | `test_every_model_has_been_classified`, `test_catalog_lint` |
| 7-8 | Lawful basis; consent | Basis per purpose; consent records with frozen notice digest, keyed chain; visitor cookie choices | `privacy.models.ConsentRecord`, `CookieConsent` | `test_lgpd`, `test_lgpd_extras` |
| 8 par. 2 | Proof of consent | Keyed hash chain, evidence hashes | `common.encryption.chain_digest` | `test_lgpd` |
| 9 | Access to information on processing | Public notice, purposes (with the consequence of refusing), sub-processors | `privacy.public_api` | `test_lgpd`, `test_lgpd_extras` |
| 11 | Sensitive data | Category `sensitive`; encrypted fields enforced by test; **restricting the allowed bases is operator work (to validate)** | `privacy.catalog.Category`, `common.encryption` | `test_catalog_lint` |
| 12 | Anonymized data | Anonymization executors; pseudonymised audit rows are kept: **whether they are personal data is to validate** | `privacy.services` | `test_lgpd` |
| 14 | Children | Category `child` (encrypted), guardian confirmation, age-assurance seam, ECA Digital notes; operator chooses the method | `privacy.age`, `ProcessingPurpose.involves_children` | `test_lgpd_extras` |
| 15-16 | End of processing; retention | Sweep with dry run; dormant accounts, uploads, keys, cookie consents; legal holds | `privacy.retention` | `test_lgpd`, `test_lgpd_retention` |
| 18 I | Confirmation | Answer says whether data is held | `privacy.services` | `test_lgpd_extras` |
| 18 II, V | Access; portability | Sealed export, limited-use link; **ANPD format still pending** (to validate) | `privacy.services` | `test_export_link` |
| 18 III | Correction | Routed to a person (`legal_review`) | `privacy.services` | `test_lgpd` |
| 18 IV, VI | Anonymization, blocking, deletion | Executors from the catalog; stored files removed; step-up by mail | `privacy.services`, `uploads.signals` | `test_lgpd`, `test_lgpd_retention` |
| 18 VII | Who data is shared with | Active sub-processors; stubs for the platform's own vendors | `privacy.public_api`, `privacy_seed` | `test_lgpd_extras` |
| 18 VIII | Consequence of refusing consent | `ProcessingPurpose.refusal_consequence`, published with the purpose | `privacy.public_api` | `test_lgpd_extras` |
| 18 IX | Withdrawal | Always possible, never throttled | `privacy.services` | `test_lgpd` |
| 19 | Response deadlines | Target days setting; reminders; overdue | `privacy.deadlines`, `privacy.jobs` | `test_lgpd` |
| 33 | International transfer | `SubProcessor.transfer_mechanism`, country; **clause texts and the ANPD standard clauses are operator work (Res. CD/ANPD 19/2024)** | `privacy.models.SubProcessor` | `test_lgpd_extras` |
| 37 | Record of processing | RoPA export from the catalog (**table level: recipients and security measures are operator text**) | `manage.py privacy_ropa` | `test_lgpd` |
| 38 | Impact report (RIPD) | `ImpactAssessment` model and template | `privacy.models.ImpactAssessment` | `test_lgpd_extras` |
| 41 | DPO | `DPO_*` published and required in production; contact endpoint | `privacy.public_api`, `settings.validators` | `test_lgpd_extras` |
| 46-47 | Security | Hardening, MFA, encryption, keyed audit, strict production validators | see [hardening](../security/hardening.md) | `test_security_regressions`, `test_hardening` |
| 48 | Incident communication | Incident model; ANPD and subjects deadlines, 20-business-day complement, small-agent doubling, content export (**clock start and 3 business days: to validate**) | `privacy.models.PersonalDataIncident`, `privacy_incident_export` | `test_lgpd`, `test_lgpd_extras` |
| 50 | Governance | Keyed audit chain, runbooks | `audit`, [runbooks](../deploy/runbooks.md) | `test_audit_integrity` |
| ECA Digital | Age assurance, privacy by default (Lei 15.211/2025) | The seam above; **applicability is a legal question** | `privacy.age` | `test_lgpd_extras` |

Not covered by software: choosing legal bases, writing notices (templates help), international
transfer clauses, RIPD content, training, contracts with processors, the controller/operator
split. The platform gives you the register, the evidence and the executors; people decide.
