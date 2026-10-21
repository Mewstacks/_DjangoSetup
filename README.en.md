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
python scripts/bootstrap.py
python manage.py runserver
```

`bootstrap` writes `.env` with fresh secrets, migrates, seeds the LGPD purposes and creates a
verified administrator, an organization and an API key (shown once). To rename the project:
`python scripts/init_project.py --name my-product`.

## Program with AI (MCP)

There are two MCP servers with different jobs:

| | For | Does | Starts with |
|---|---|---|---|
| `saas-devtools` | Whoever **builds** the product (Claude Code, Cursor, Codex) | Teaches the project to the AI: rules, framework, middleware, LGPD; generates resources; runs the gate | `python -m devtools.mcp` (stdio, local only) |
| `/mcp` | Whoever **uses** the running product (customers' agents) | Every action becomes a tool, with scope, role and audit | `MCP_ENABLED=true`, inside the server |

### 1. Connect the development agent

The root `.mcp.json` already registers `saas-devtools`.

- **Claude Code:** open the project at its root and approve the server when asked (or
  `claude mcp add saas-devtools -- uv run python -m devtools.mcp`). `/mcp` shows its state.
- **Cursor, Codex and others:** register the same command (`uv run python -m devtools.mcp`, with
  `DJANGO_SETTINGS_MODULE=config.settings.local`) in the client's MCP file.

`CLAUDE.md`, `AGENTS.md` and `.cursor/rules` already tell the AI to follow the project's rules.

### 2. Ask for the feature

> Add an "invoices" resource with title, amount and due date. Use the project's MCP.

The AI follows this path (the tools belong to `saas-devtools`):

1. `describe_project` and `list_conventions`: learns the apps, the rules and the definition of done.
2. `framework_guide` and `middleware_stack`: looks up how Django, DRF, Temporal and the middleware
   work here, when it needs to.
3. `scaffold_resource` (`dry_run` first): generates model, service, actions, undo, events, LGPD entry
   and tests.
4. `lgpd_check`: decides category, purpose and erasure for every personal field.
5. `check_conventions` and `run_gate`: fixes until green. Nothing is done while the gate is red.

You review the diff. Without MCP it works the same way: `python manage.py scaffold resource ...` and
`python scripts/verify.py --fast`.

### 3. Expose the product to customers' agents

```bash
MCP_ENABLED=true OAUTH_ENABLED=true python manage.py runserver
python manage.py mcp_config --url http://localhost:8000 --org acme
```

`mcp_config` prints ready-made snippets for Claude Code, Cursor and a curl check. The API key from
`bootstrap` authenticates; its scopes limit the tools. Details in the
[MCP guide](docs/en/guides/mcp.md) and the [AI guide](docs/en/guides/ai-development.md).

## Quality

`python scripts/verify.py` runs lint, types, tests, migrations and the drift checks (action
catalog, OpenAPI, generated docs). CI adds PostgreSQL, pip-audit, bandit, gitleaks, zizmor,
hadolint, Trivy, CodeQL and an SBOM.

## Notice

The technical controls help with security and accountability evidence but do not make a product
automatically LGPD-compliant. Each system still needs its own purposes, lawful bases, retention,
vendors, privacy notices and accountable owners. See the
[compliance matrix](docs/en/lgpd/compliance-matrix.md).

Security: [SECURITY.md](SECURITY.md). Changes: [CHANGELOG.md](CHANGELOG.md). License: MIT.
