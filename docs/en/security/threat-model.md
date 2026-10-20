# Threat model

| Asset | Threat | Control |
|---|---|---|
| Another organization's data | IDOR, missing tenant filter, writable foreign key to a foreign row | Single ORM door in actions (`ctx.scoped`, AST test), `OrganizationScopedViewSet`, `OrgScopedPrimaryKeyRelatedField`, role checked per call |
| Credentials | Brute force, stuffing, enumeration | Argon2, axes lockout (IPv6 /64 buckets), allauth rate limits, uniform responses, MFA |
| API keys | Theft, over-privilege, key-mints-key | Blind-index storage, scopes default-deny, IP allow-list, expiry, session-only creation, 24 h rotation overlap |
| Tokens (OAuth) | Replay at another service | PKCE, audience binding (RFC 8707), short lifetime |
| Secrets in the database | Dump or backup leak | AES-GCM field encryption with key ring and rotation (`reencrypt_fields`), encrypted MFA seeds, idempotency responses and undo snapshots |
| Logs and traces | PII leakage | Redaction at the end of the pipeline, golden-log test, Temporal payload encryption |
| Outbound calls | SSRF, DNS rebinding | `netguard`: https, public addresses, pinned IP, no redirects |
| Uploads | Malware, polyglots, zip bombs, stored XSS | Content sniffing, extension/second-extension rules, zip limits, attachment + nosniff + CSP sandbox, optional ClamAV |
| Audit trail | Tampering | Hash chain per organization, DB trigger blocks UPDATE/DELETE, anchors on prune, `audit_verify` |
| Availability | Large bodies, floods | ASGI body cap, per-IP and per-credential budgets, bounded responses |
| Supply chain | Vulnerable or malicious dependency | Locked deps, pip-audit, Dependabot, SBOM, pinned Actions and images, Trivy, provenance |
| Agents (MCP) | Prompt-injected destructive actions | Scopes, role, `destructive` hints, undo journal, run ledger, text in records treated as data |

Out of scope: a compromised host or build pipeline, malicious superusers (mitigated by audit and
admin allow-list, not prevented), SSO/SCIM.
