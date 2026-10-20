# Multi-tenant Django platform

[Português](README.md) · [Documentation](docs/en/index.md)

A base for systems of any kind: Django 6.1, DRF, PostgreSQL, multi-tenant, with API and MCP
ready, optional Temporal, strict security and LGPD tooling.

**One function you write becomes** a REST endpoint, an MCP tool, a Temporal activity and a CLI
command, with scope, role, rate limit, idempotency, audit and undo.

```python
@action("notes.create", write=True)
def create_note(ctx: ActionContext, data: CreateNote) -> NoteOut:
    """Create a note."""
    return NoteOut.of(services.create_note(ctx, title=data.title, body=data.body))
```

## What is included

| | |
|---|---|
| Actions and API | Action registry, REST at `/api/v1/actions/`, committed OpenAPI |
| MCP | Stateless server at `/mcp`, OAuth 2.1 with PKCE and dynamic registration, API keys |
| Accounts | allauth: switchable sign-up, verified e-mail, MFA (TOTP, WebAuthn), sessions |
| Flows | Temporal (encrypted, context-propagating) or a local engine; scheduled jobs |
| LGPD | Mandatory data catalog, consent, data subject requests, retention, incidents, RoPA |
| Security | Strict production validators, field encryption with rotation, hash-chained audit, SSRF-safe |
| Extras | Webhooks with outbox, feature flags, typed settings, validated uploads |
| Operations | PII-free JSON logs, OpenTelemetry, `doctor`, one image with roles, compose, Kubernetes, Procfile |

## Get started

```bash
uv sync --all-extras
python scripts/init_local.py --sqlite
python manage.py migrate && python manage.py createsuperuser
python manage.py runserver
```

Then: [quickstart](docs/en/quickstart.md), [architecture](docs/en/architecture.md),
[add an action](docs/en/guides/add-an-action.md).

## Quality

`python scripts/verify.py` runs lint, types, tests, migrations and the drift checks (action
catalog, OpenAPI, generated docs). CI adds PostgreSQL, pip-audit, bandit, gitleaks, zizmor,
hadolint, Trivy, CodeQL and an SBOM.

## Notice

The technical controls help with security and accountability evidence but do not make a product
automatically LGPD-compliant. Each system still needs its own purposes, lawful bases, retention,
vendors, privacy notices and accountable owners. See the
[compliance matrix](docs/en/lgpd/compliance-matrix.md).

Security: [SECURITY.md](SECURITY.md). Changes: [CHANGELOG.md](CHANGELOG.md).
