# LGPD compliance matrix

Article → platform feature → code → test. "Operator" means the organization running the system
must still do something. Interpretations are marked **to validate**.

| Art. | Requirement | Platform | Code | Test |
|---|---|---|---|---|
| 6 | Principles (purpose, necessity, security) | Purposes with retention; classification forces a decision per model | `privacy.models.ProcessingPurpose`, `privacy.catalog` | `test_every_model_has_been_classified` |
| 7-8 | Lawful basis; consent | Basis per purpose; consent records with frozen notice digest, chain | `privacy.models.ConsentRecord` | `test_lgpd` (consent chain, withdrawal) |
| 9 | Access to information on processing | Public notice, purposes, sub-processors | `privacy.public_api` | `test_lgpd` (public endpoints) |
| 11 | Sensitive data | Category `sensitive`; encrypted fields | `privacy.catalog.Category`, `common.encryption` | `test_security_regressions` |
| 14 | Children | Category `child`; operator defines guardian flow | catalog | catalog test (operator) |
| 15-16 | End of processing; retention | Sweep with dry run; legal holds | `privacy.retention` | `test_lgpd` (retention) |
| 18 | Subject rights | 11 request types, executors, SLA | `privacy.services`, `privacy.workflows` | `test_lgpd` (requests end to end) |
| 18 V | Portability | Export package; **ANPD format still pending** (to validate) | `privacy.services` | export test |
| 19 | Response deadlines | Target days setting; reminders; overdue | `privacy.deadlines`, `privacy.jobs` | `test_lgpd` (SLA) |
| 37 | Record of processing | RoPA export from the catalog | `manage.py privacy_ropa` | `test_lgpd` |
| 38 | Impact report (RIPD) | Operator: the catalog and RoPA are inputs | - | - |
| 41 | DPO | `DPO_*` published; contact endpoint | `privacy.public_api` | public endpoint test |
| 46-47 | Security | Hardening, MFA, encryption, strict production validators | see [hardening](../security/hardening.md) | `test_security_regressions` |
| 48 | Incident communication | Incident model, business-day deadline, reminders (**3 business days: to validate**) | `privacy.deadlines`, `PersonalDataIncident` | `test_lgpd` (deadlines) |
| 50 | Governance | Audit chain, runbooks | `audit`, [runbooks](../deploy/runbooks.md) | `test_audit_integrity` |

Not covered by software: choosing legal bases, writing notices, international transfer clauses,
RIPD content, training, contracts with processors. The platform gives you the register, the
evidence and the executors; people decide.
