# Platform documentation

A Django 6 base for multi-tenant systems of any kind. One function you write becomes a REST
endpoint, an MCP tool, a Temporal activity and a CLI command, with authentication, auditing and
Brazilian data-protection (LGPD) tooling already in place.

| Start here | |
|---|---|
| [Quickstart](quickstart.md) | Run it locally and call your first action |
| [Architecture](architecture.md) | The pieces and how a request travels through them |
| [Add an action](guides/add-an-action.md) | The 10-minute path to a new capability |

## Guides

- [Add a flow or a job](guides/add-a-flow.md) - Temporal, or the local engine when it is off
- [MCP server](guides/mcp.md) - connect Claude, Cursor and other agents
- [Accounts, API keys and OAuth](guides/auth.md)
- [Webhooks](guides/webhooks.md), [feature flags and settings](guides/flags-and-settings.md),
  [uploads](guides/uploads.md)
- [Observability](guides/observability.md), [testing](guides/testing.md)

## LGPD

- [Overview](lgpd/overview.md) and [compliance matrix](lgpd/compliance-matrix.md)

## Security

- [Threat model](security/threat-model.md), [hardening](security/hardening.md),
  [audit integrity](security/audit-integrity.md), [review](security/review.md)

## Deploying

- [Deploy anywhere](deploy/overview.md), [runbooks](deploy/runbooks.md)
- [Upgrading from the Celery-era template](migration/from-celery.md)

## Reference (generated)

[Environment variables](reference/env-vars.md) - [Actions and MCP tools](reference/actions.md) -
[REST endpoints](reference/api.md) - [Flow engines](reference/engines.md) -
[Personal data catalog](reference/data-catalog.md) - [Decisions](adr/index.md)
