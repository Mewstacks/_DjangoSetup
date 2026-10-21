# Threat model

| Asset | Threat | Control |
|---|---|---|
| Another organization's data | IDOR, missing tenant filter, writable foreign key to a foreign row | Single ORM door in actions (`ctx.scoped`, AST test over `actions.py`, `actions/*.py`, `agent.py`), `OrganizationScopedViewSet`, `OrgScopedPrimaryKeyRelatedField`, every organization column scoped or explained (test), undo filters by organization, role checked per call; row-level security is a documented option ([ADR 14](../adr/row-level-security.md)) |
| Shared capacity | One tenant fills the database, the bucket or the key table | Per-organization quotas (`QUOTA_*`) |
| Credentials | Brute force, stuffing, enumeration | Argon2, axes lockout on every sign-in path (IPv6 /64 buckets), allauth rate limits, uniform responses, MFA |
| Privileged accounts | Staff-to-superuser takeover; admin with a password alone | Superusers hidden from other staff, e-mail and password views superuser-only, MFA required for the admin and (production) for owners and administrators |
| API keys | Theft, over-privilege, key-mints-key, survival of a takeover | Keyed blind-index storage, scopes default-deny, validated IP allow-list, expiry, session-only creation with a recent sign-in, 24 h rotation overlap, revoked on password / MFA reset, failures counted per key+address |
| Tokens (OAuth) | Replay at another service; database dump | PKCE `S256`, audience binding (RFC 8707), stored as checksum, rotating refresh with family revocation, RFC 9207 `iss`, https/loopback redirects only, throttled and policy-checked registration |
| Secrets in the database | Dump or backup leak | AES-GCM field encryption with key ring and rotation (`reencrypt_fields`, MFA seeds included), encrypted idempotency responses and undo snapshots, tokens as checksums |
| Logs and traces | PII leakage | Redaction at the end of the pipeline (including objects rendered with `str`), secret URL paths scrubbed, golden-log test, Temporal payload encryption |
| Outbound calls | SSRF, DNS rebinding, tunnelled private addresses | `netguard`: https, global addresses only, pinned IP, no redirects, no env proxy, deadline, no decompression; NetworkPolicy egress excludes private ranges |
| Data subject export | A mailed link that outlives its purpose | Sealed archive, expiring link capped at `PRIVACY_EXPORT_MAX_DOWNLOADS`, token scrubbed from logs, absolute `PUBLIC_URL` |
| Uploads | Malware, polyglots, zip bombs, stored XSS, orphaned files | Content sniffing, extension rules, zip limits, attachment + nosniff + CSP sandbox, optional ClamAV, file removed with its row on every path |
| Audit trail | Tampering by a compromised app account or by a database writer | Keyed hash chain per organization, owner-only prune function, runtime role with `INSERT`/`SELECT` only, `CHECK` against rows outside the chain, `audit_verify` and head export ([ADR 13](../adr/audit-chain-and-role-split.md)) |
| Workflow engine | A stranger on the Temporal network starts an activity as anyone | Sealed payloads required (an unsealed one is refused), TLS or API key validated at boot, `run_task` limited to declared tasks under allowed prefixes |
| Availability | Large or slow bodies, floods | ASGI body cap and read timeout, per-IP and per-credential budgets, bounded responses |
| Supply chain | Vulnerable or malicious dependency, tampered image | Locked deps, weekly `pip-audit` of `uv.lock`, Dependabot, SBOM, pinned Actions and images, Trivy, CodeQL, zizmor, release gated on CI, cosign signature, provenance, deploy by digest |
| Agents (MCP) | Prompt-injected destructive actions | Scopes, role, `destructive` hints, an explicit undo decision per write action, undo journal, run ledger, text in records treated as data, behaviour prompt |
| The codebase itself | A change (human or AI) that removes a control | Rules enforced by tests, conformance suite over every action, generated agent files kept fresh, `check_conventions` |

Out of scope: a compromised host or build pipeline, malicious superusers who also hold the keys
(mitigated by audit and the admin allow-list, not prevented), SSO/SCIM, denial of service at the
network layer.
