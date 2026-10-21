# Platform documentation

A Django 6 base for multi-tenant systems of any kind. One function you write becomes a REST
endpoint, an MCP tool, a Temporal activity and a CLI command, with authentication, auditing and
Brazilian data-protection (LGPD) tooling already in place, and a rulebook an engineer or an AI
coding agent can follow.

| Start here | |
|---|---|
| [Quickstart](quickstart.md) | Run it locally and call your first action |
| [Start a product](guides/start-a-product.md) | From a clone to a deployed product, in order |
| [Building with an AI coding agent](guides/ai-development.md) | `AGENTS.md`, the development MCP server, the scaffold |
| [Architecture](architecture.md) | The pieces and how a request travels through them |
| [Framework primer](guides/framework-primer.md) | Django, DRF, Temporal and the middleware order, with this project's rules |
| [Add an action](guides/add-an-action.md) | The 10-minute path to a new capability |

## Guides

- [Add a flow or a job](guides/add-a-flow.md) - Temporal, or the local engine when it is off
- [MCP server](guides/mcp.md) - connect Claude, Cursor and other agents to a running product
- [Accounts, API keys and OAuth](guides/auth.md), [roles and permissions](guides/roles-and-permissions.md)
- [Frontend and SPA integration](guides/frontend.md), [API conventions](guides/api-conventions.md)
- [Webhooks](guides/webhooks.md), [feature flags and settings](guides/flags-and-settings.md),
  [uploads](guides/uploads.md), [e-mail and languages](guides/email-and-i18n.md)
- [Billing and plans](guides/billing.md), [offboarding a tenant](guides/offboarding.md)
- [Observability](guides/observability.md), [testing](guides/testing.md),
  [management commands](guides/commands.md), [troubleshooting](guides/troubleshooting.md)
- [Upgrading from upstream](guides/upgrading.md)

## LGPD

- [Overview](lgpd/overview.md), [compliance matrix](lgpd/compliance-matrix.md) and
  [document templates](lgpd/templates.md)

## Security

- [Threat model](security/threat-model.md), [hardening](security/hardening.md),
  [audit integrity](security/audit-integrity.md), [review](security/review.md),
  [builder's checklist](security/builder-checklist.md)

## Deploying

- [Deploy anywhere](deploy/overview.md), [runbooks](deploy/runbooks.md)
- [Upgrading from the Celery-era template](migration/from-celery.md)

## Reference (generated)

[Environment variables](reference/env-vars.md) - [Actions and MCP tools](reference/actions.md) -
[REST endpoints](reference/api.md) - [Flow engines](reference/engines.md) -
[Personal data catalog](reference/data-catalog.md) - [Decisions](adr/index.md)

For AI agents: `AGENTS.md` and `llms.txt` at the repository root.
