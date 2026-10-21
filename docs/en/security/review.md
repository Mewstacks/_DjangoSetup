# Security review

Status of the review of this template. Update this page whenever you change authentication,
tenancy, cryptography, logging or the outbound client.

## Baseline (start of the program): 36 findings

Two high severity (client IP collapsing behind a proxy, so throttles and lockouts were shared;
consent withdrawal could be blocked), the rest medium and low. All were fixed with a named
regression test in `tests/test_security_regressions.py`.

## Second review (2026-10)

A static review of settings, accounts, tenancy, audit, webhooks, flows, deployment and CI. Every
finding below was fixed with a named test unless noted.

| Severity | Finding | Resolution | Test |
|---|---|---|---|
| High | The `uploads` app was untracked: an unanchored `.gitignore` rule hid it, so a clean clone could not start | Rules anchored; CI fails on ignored files under `src/` | CI step; `test_scaffold` copies the tree |
| High | Audit trail: any session could delete after setting a GUC; the hash was unkeyed; newest rows unverifiable; forged inserts outside the chain | Keyed HMAC chain, owner-only `audit_prune()`, role separation, `CHECK`, head export | `test_audit_integrity`, `test_the_chain_is_keyed...`, role-separation test (PostgreSQL) |
| Medium | SSRF guard missed carrier-grade NAT (100.64/10, Alibaba metadata), NAT64/6to4/Teredo wrappers; proxy from the environment; no total deadline; decompression | Allow-list of global addresses, embedded-IPv4 check, `trust_env=False`, deadline, raw bytes only | `test_netguard` |
| Medium | Staff with `change_user` could take over a superuser (edit the e-mail, reset) | Superusers hidden, e-mail read-only, password view superuser-only | `test_hardening` |
| Medium | No MFA for staff or owners; no recent sign-in to mint a key; keys survived a reset | `STAFF_MFA_REQUIRED`, `ORG_PRIVILEGED_MFA_REQUIRED`, recent-auth window, revoke on reset | `test_hardening` |
| Medium | OAuth tokens stored in clear; no refresh-replay protection; DCR accepted `client_credentials`, `http` redirects and never expired | RFC 9700 gates on, checksum storage, reuse protection, registration policy and expiry, `iss` | `test_hardening`, `test_oauth`, `test_mcp_protocol` |
| Medium | Temporal accepted unsealed payloads (forgeable activity input); `run_task` imported any dotted path; no boot validation | Unsealed refused, task bridge restricted, validators | `test_flows`, `test_hardening` |
| Medium | Key rotation missed MFA seeds; MFA decrypt accepted plaintext; HMAC rotation broke every key | `reencrypt_fields` covers MFA, plaintext refused, `PRIVACY_HMAC_KEYS_PREVIOUS`, `SECRET_KEY_FALLBACKS` | `test_key_rotation` |
| Medium | Export link reusable for 7 days, relative in the mail, token in the URL path of logs | Download cap, absolute `PUBLIC_URL`, token scrubbed | `test_export_link` |
| Medium | Failed-login and refused-action audit rows were attacker-controlled in volume; per-id key lockout let a stranger lock out the owner | Per-client ceilings, per-address failure counters | `test_abuse_limits` |
| Medium | Deployment: open egress, one superuser database identity for everything, `:latest`, unencrypted backups, no release gate | NetworkPolicy ipBlock, two roles, digests, umask and TLS on backups, release gated on CI with signing | CI (render, trivy config, boot) |
| Low | No Permissions-Policy / CORP; CORS covered every path; no CSP sink; admin path without slash leaked; html 500s for the API; objects bypassed log redaction; legacy login | Added, scoped, or switched off | `test_web_hardening` |
| Low | Tenant isolation was convention only; undo looked up the target by id alone; unbounded per-tenant resources | Structural tests, organization filter in undo, quotas | `test_tenancy_structure` |
| Low | Database TLS `require` and Redis password-only accepted; slow request bodies; deploy check passed on warnings | Verified TLS, `rediss`, 408 on stalled bodies, warnings fail | `test_security_regressions`, `test_body_timeout` |

## Open items

| Item | Notes |
|---|---|
| Row-level security | A documented option, not implemented ([ADR 14](../adr/row-level-security.md)) |
| Breached-password check | Not built: it needs an outbound call to a third party; add it as an allauth password validator through `netguard` if you want it |
| Idle session timeout | Sessions have an absolute lifetime (`SESSION_COOKIE_AGE_SECONDS`, 12 h); add a sliding idle limit if your threat model asks |
| Per-user authorization for flows | A flow runs as the person who started it with that person's role, but not with the starting credential's scopes: declare each flow's scope to cover everything it does |
| Image base digests | The application image is signed and deployed by digest; pin the base image by digest in your registry mirror for byte-for-byte rebuilds |
| Per-user AAD for MFA secrets | allauth's adapter hook passes no user, so seeds are bound to the column, not the person |
| `AUDIT_HMAC_KEY` rotation | New epoch, no tooling yet ([ADR 13](../adr/audit-chain-and-role-split.md)) |

Report vulnerabilities as described in `SECURITY.md`.
