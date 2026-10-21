# Changelog

Português: [CHANGELOG.pt-BR.md](CHANGELOG.pt-BR.md)

## 2.1.0 - 2026-10-21 - security, LGPD and AI-buildable revision

Breaking (no production deployments existed, formats changed in place): audit rows are now chained
with a keyed HMAC and need `AUDIT_HMAC_KEY`; the runtime database role can no longer prune or
rewrite the audit trail; write actions must declare `undoable`; production requires `PUBLIC_URL`,
`PRIVACY_CONTROLLER_NAME`, a DPO contact and a declared proxy; `DEV_TOOLS_ALLOWED` replaces the old
dev-tools flag. See [upgrading](docs/en/guides/upgrading.md).

### Added
- Development MCP server (`python -m devtools.mcp`), `manage.py scaffold`, generated `AGENTS.md`,
  `CLAUDE.md`, Cursor and Copilot rules, `llms.txt`, `llms-full.txt`, `conventions.json`.
- Runtime MCP resources `platform://actions` and `platform://scopes`, and a usage prompt.
- Conformance suite parametrised over every registered action; catalog lint; tenancy structure test.
- `scripts/bootstrap.py`, `init_project.py`, `remove_example.py`; `justfile`, `.editorconfig`,
  `.python-version`, CODEOWNERS, issue and PR templates, MIT `LICENSE`.
- LGPD: cookie-consent log, impact assessments (RIPD), incident deadlines and export, dormant-account
  retention, upload blob erasure, age-assurance hook, refusal consequences, pt-BR e-mails.
- Docs: eleven new guides, five ADRs, four document templates, builder checklist (en and pt-BR).
- CI: weekly schedule, Python matrix, ignored-file guard, Trivy, cosign signing, attestations,
  GitHub Release gate.

### Changed
- Network guard allows only globally routable addresses (CGNAT, NAT64 and 6to4 forms were gaps).
- Staff and privileged organization roles need MFA; API keys are revoked on password reset;
  key minting needs recent sign-in.
- OAuth: hashed token storage, RFC 9207 `iss`, DCR policy; MCP verifier reads the real client IP.
- Temporal: unsealed payloads refused, TLS or API key required, task bridge restricted to declared
  prefixes, flows carry their own scope.
- Privacy export links are single-use; URLs are scrubbed from logs.
- CSP, Permissions-Policy and CORP headers; JSON error handlers; body-read timeout.
- Deploy: separate migrator and runtime database roles, NetworkPolicy egress limits, hardened pods.

### Fixed
- `.gitignore` excluded `src/apps/uploads/`, so a clean clone could not boot.
- Production templates read bucket variables the docs did not mention.

## 2.0.0 - platform release

Breaking: read [the migration guide](docs/en/migration/from-celery.md).

### Added
- Action kernel (`@action`) exposed as REST, MCP, Temporal activity and CLI; undo journal and
  agent run ledger; idempotency keys.
- API keys, OAuth 2.1 (PKCE, dynamic registration) and an MCP server.
- Accounts on django-allauth: closed-by-default sign-up, verified e-mail, TOTP/WebAuthn MFA,
  device sessions, minimal sign-in and consent pages.
- Flows and jobs on Temporal (encrypted payloads, context propagation, Schedules,
  `TemporalTaskBackend`) or a local engine; `run_scheduler` for cron-style jobs.
- Hash-chained audit trail per organization with a database trigger and `audit_verify`.
- LGPD: data catalog with a failing test for unclassified models, consent chain, data subject
  requests with executors and SLA, retention with legal holds, incidents, RoPA export.
- Webhooks with transactional outbox, feature flags, typed settings, validated uploads.
- structlog pipeline with redaction, OpenTelemetry, `doctor`, health probes.
- One image with roles, production compose, Kubernetes manifests, Procfile, S3-compatible storage.
- CI: dependency audit, bandit, gitleaks, zizmor, hadolint, Trivy, CodeQL, SBOM, provenance,
  Dependabot. Generated reference docs with drift checks.

### Changed
- Django 6.1.2, DRF 3.18; strict production validators; encryption v2 (v1 still decrypts).

### Removed
- Celery, Fly.io-specific configuration and documentation.

### Security
- 36 baseline findings fixed with regression tests; see
  [the review](docs/en/security/review.md).
