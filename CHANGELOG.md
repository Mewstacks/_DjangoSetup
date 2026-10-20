# Changelog

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
