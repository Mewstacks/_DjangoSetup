# Catálogo de dados pessoais

> Gerado por `python scripts/gen_docs.py`. Não edite à mão.

| Modelo | Dado pessoal | Campos | Finalidade | Campo de retenção | Na eliminação |
|---|---|---|---|---|---|
| `account.emailaddress` | sim | email (contact), user (identifier) | account-and-access |   | delete |
| `account.emailconfirmation` | sim | key (credential) | account-and-access | created | delete |
| `accounts.user` | sim | email (contact), full_name (identifier), password (credential), last_login (behavior) | account-and-access |   | anonymize |
| `actions.actionjournal` | sim | label (content), before_json (content), after_json (content) | security-and-audit | created_at | delete |
| `actions.agentrun` | sim | summary (content), note (content) | security-and-audit | started_at | delete |
| `actions.idempotencyrecord` | sim | response_json (content) | product-content | created_at | delete |
| `admin.logentry` | sim | object_repr (content), change_message (content) | security-and-audit | action_time | delete |
| `apikeys.apikey` | sim | label (content), allowed_ips (technical) | account-and-access |   | delete |
| `audit.auditanchor` | não | A chain position and a hash. |   |   |   |
| `audit.auditevent` | não | Pseudonymous by construction: actor and organization are ids, IPs are HMACs, metadata is validated to hold no personal data. Erasing a person leaves ids that resolve to nothing. |   |   |   |
| `auth.group` | não | Role definitions, not people. |   |   |   |
| `auth.permission` | não | Permission definitions, not people. |   |   |   |
| `axes.accessattempt` | sim | username (identifier), ip_address (technical) | security-and-audit | attempt_time | delete |
| `axes.accessattemptexpiration` | não | Expiry timestamps only. |   |   |   |
| `axes.accessfailurelog` | sim | username (identifier), ip_address (technical) | security-and-audit |   | delete |
| `axes.accesslog` | sim | username (identifier), ip_address (technical) | security-and-audit |   | delete |
| `contenttypes.contenttype` | não | Model registry. |   |   |   |
| `examples.note` | sim | title (content), body (content) | product-content | created_at | anonymize |
| `flags.flag` | não | A feature switch. |   |   |   |
| `flags.flagrule` | sim | user (identifier) | product-content |   | delete |
| `flags.setting` | não | A runtime configuration value for the product or an organization. |   |   |   |
| `flows.flowrun` | sim | input_json (content), result_json (content) | security-and-audit | created_at | delete |
| `mfa.authenticator` | sim | data (credential), user (identifier) | account-and-access |   | delete |
| `oauth2_provider.accesstoken` | sim | user (identifier), scope (technical) | account-and-access |   | delete |
| `oauth2_provider.application` | não | A registered client (software), not a person; the platform never sets its owner. |   |   |   |
| `oauth2_provider.devicegrant` | sim | user (identifier), scope (technical) | account-and-access |   | delete |
| `oauth2_provider.grant` | sim | user (identifier), scope (technical) | account-and-access |   | delete |
| `oauth2_provider.idtoken` | sim | user (identifier), scope (technical) | account-and-access |   | delete |
| `oauth2_provider.refreshtoken` | sim | user (identifier) | account-and-access |   | delete |
| `organizations.membership` | sim | role (technical) | account-and-access |   | anonymize |
| `organizations.organization` | não | A tenant record (name, slug). Where the tenant is a person, the name is account data already covered by that person's User row and erased with the organization. |   |   |   |
| `privacy.consentrecord` | sim | evidence (technical) | compliance-records |   | keep |
| `privacy.datasubject` | sim | email (contact) | compliance-records |   | anonymize |
| `privacy.datasubjectrequest` | sim | details (content), response_summary (content) | compliance-records |   | keep |
| `privacy.legalhold` | sim | reason (content) | compliance-records |   | keep |
| `privacy.personaldataincident` | sim | summary (content), risk_assessment (content) | compliance-records |   | keep |
| `privacy.privacynotice` | não | The published notice text reference. |   |   |   |
| `privacy.privacyreminder` | não | Bookkeeping of reminders sent. |   |   |   |
| `privacy.processingpurpose` | não | Configuration: why we process, not about a person. |   |   |   |
| `privacy.subprocessor` | não | Vendors, not people. |   |   |   |
| `sessions.session` | não | Opaque signed session data; expires on its own and is deleted with the account's sessions when the subject is erased (see apps.privacy.services). |   |   |   |
| `uploads.uploadedfile` | sim | file (content), original_name (content), uploaded_by (identifier) | product-content |   | delete |
| `usersessions.usersession` | sim | ip (technical), user_agent (technical) | security-and-audit |   | delete |
| `webhooks.webhookdelivery` | não | Delivery bookkeeping: status codes and counters. |   |   |   |
| `webhooks.webhookendpoint` | não | A receiver URL and its signing secret (encrypted); no person. |   |   |   |
| `webhooks.webhookevent` | sim | payload_json (content) | product-content | created_at | delete |
