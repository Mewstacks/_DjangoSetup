# Security review

Status of the review of this template. Update this page whenever you change authentication,
tenancy, cryptography, logging or the outbound client.

## Baseline (start of the program): 36 findings

Two high severity (client IP collapsing behind a proxy, so throttles and lockouts were shared;
consent withdrawal could be blocked), the rest medium and low. All were fixed with a named
regression test in `tests/test_security_regressions.py`, except those carried below.

## Reviews during the build

| Area | Finding | Resolution |
|---|---|---|
| Admin | Membership inline allowed self-escalation | Inline restricted; superuser-only fields |
| API keys | Rotate callable by non-owner | Owner-only |
| Flows | `flows.start` accepted identity from input | Engine stamps identity; input with identity keys rejected |
| LGPD | Destructive request executed on one POST | Verification step by mailed link |
| Logging | Native structlog events skipped redaction | Redaction moved to the final processors |
| Webhooks | Endpoint list leaked the decrypted secret | Secret returned only on create/rotate; test added |
| Accounts | Legacy login could bypass MFA and e-mail verification | Refuses such accounts; admin login via allauth |
| Pages | Sessions page crashed (missing `humanize`) | App added; render tests for every account page |
| OAuth consent | CSP `form-action 'self'` blocks the post-consent redirect in Chrome | Consent view alone omits the directive; test asserts every other page keeps it |

## Open items

| Item | Notes |
|---|---|
| Audit coverage gaps | Some admin-side changes are audited through `AuditedAdminMixin`; custom admin actions must call `record_event` |
| CSP reporting and nonces | CSP is `'self'`-only for the shipped pages; add a report endpoint before introducing inline scripts |
| Image build in CI | The image pipeline is written but its first run happens in your repository |
| Docker image digest pin | Base image is pinned by tag; pin by digest in your registry mirror |

Report vulnerabilities as described in `SECURITY.md`.
