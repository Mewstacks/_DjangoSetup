# ADR 15: Two MCP servers, with different jobs

**Status:** accepted.

## Context

"An MCP server" was one idea with two audiences. An AI agent can be asked to **operate a running
product** for a person (read their notes, create an invoice), or to **build the product** (add a
resource, fix a bug). The risks, the identity and the lifetime differ.

## Decision

- **Platform MCP** (`/mcp`, in the deployed service). Tools are the actions marked for the `mcp`
  channel; identity is a person's API key or OAuth token; every call is audited; writes can be
  undone. It also serves `platform://actions`, `platform://scopes` and a behaviour prompt.
- **Development MCP** (`python -m devtools.mcp`, on the developer's machine, stdio). No identity: it
  reads the rulebook, the registries and the docs, scaffolds code, checks conventions and runs the
  gate. It writes only under `src/` and `tests/`, only on request, and is never mounted in a
  deployed service.

They share nothing at runtime. The development server reuses the same registries (actions, data
catalog) so what an agent learns about the code is what the platform enforces.

## Consequences

- A leaked development server is a local file-write capability, not access to customer data, because
  it has no database credentials of its own beyond the developer's local settings.
- The platform server's attack surface does not grow with developer tooling.
- The development server's tools are the first thing to update when a convention changes: they read
  `src/devtools/conventions.py`, the same source as `AGENTS.md`.
