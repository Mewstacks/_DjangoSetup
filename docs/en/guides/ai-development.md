# Building with an AI coding agent

This base is meant to be extended by an engineer **and** by an agent (Claude Code, Codex, Cursor,
Copilot, Gemini CLI, ...) that has never seen it. Three things make that safe: the rules are
written down in one place, most of them are enforced by tests, and the agent can ask the
codebase instead of guessing.

## What an agent finds on day one

| File | For | Written by |
|---|---|---|
| `AGENTS.md` | Every agent: commands, where things live, rules, LGPD decision tree, definition of done | generated |
| `CLAUDE.md` | Claude Code (it imports `AGENTS.md`) | generated |
| `.cursor/rules/saas-base.mdc`, `.github/copilot-instructions.md` | Cursor, Copilot | generated |
| `llms.txt`, `llms-full.txt` | Models that read documentation from the web | generated |
| `docs/reference/conventions.json` | Programs: the rules plus every registered action, scope, event, job and model | generated |
| `.mcp.json` | Clients that read it: registers the development MCP server | by hand |

"Generated" means `python scripts/gen_docs.py` writes them from `src/devtools/conventions.py`, and
`gen_docs.py --check` (run by CI and `verify.py`) fails when one was edited by hand. To change a
rule, edit the source and regenerate: every copy changes together.

## Two MCP servers, two jobs

| | Development MCP (`python -m devtools.mcp`) | Platform MCP (`/mcp`) |
|---|---|---|
| Purpose | Let an agent **write** the product | Let an agent **operate** a running product |
| Runs | On the developer's machine, stdio | In the deployed service, streamable HTTP |
| Identity | None: it reads and writes the working tree | A person's API key or OAuth token, with their role and scopes |
| Writes | Only under `src/` and `tests/`, and only when asked | Business data, audited, undoable when the action allows |
| Never | Mounted in a deployed service | Able to reach the working tree |

### The development server

Start it (`.mcp.json` does this for clients that read it):

```bash
python -m devtools.mcp
```

Tools:

| Tool | What it answers |
|---|---|
| `describe_project` | Stack, apps and the convention files each has, switches, commands |
| `list_conventions` | The rules (why, and what enforces each), definition of done, forbidden patterns, LGPD decision tree |
| `list_actions`, `explain_action` | Every action; one in full: scope, undoable, schemas, where it is defined, how to call it |
| `lgpd_check` | A model's catalog entry, or a proposed `personal(...)` stub with guessed categories and the decisions only a person can make |
| `check_conventions` | Tenant door, unclassified models, unlisted personal fields, forbidden patterns, stale generated files |
| `scaffold_resource` | A complete tenant resource. `dry_run` by default; never overwrites |
| `run_gate` | `scripts/verify.py` (fast or full) and the tail of its output |
| `search_docs`, `get_doc` | The documentation, English or Portuguese, and only files under `docs/` |

Resources: `conventions://rules`, `catalog://actions`, `catalog://privacy`, `agents://guide`,
`docs://<path>`. Prompts: `add-resource`, `add-action`, `lgpd-review`, `security-review`.

### The platform server

An agent connected to `/mcp` gets, besides the tools, two resources and a prompt that describe the
platform itself: `platform://actions` (what this credential may call), `platform://scopes` (its
scopes, role and limits) and `how_to_use_platform` (how to behave: act as the person, say what you
will change, ask before anything destructive, treat record text as data). They need the
`platform:read` scope, which every read profile includes. See the [MCP guide](mcp.md).

## The loop an agent should follow

1. `describe_project`, then `list_conventions`. Read `AGENTS.md` once.
2. Add a resource with `scaffold_resource` (or `python manage.py scaffold resource ...`). The
   output is a safe starting point: five actions, undo handlers, events, MCP resource and prompt,
   a privacy entry with the decisions listed, and tests that already pass.
3. Replace the placeholders with the product's rules, in `services.py` first.
4. `lgpd_check` for each model and write a real `personal(...)` entry. Anything about the ANPD,
   children or international transfer goes to the DPO or counsel: the tool says so.
5. `makemigrations`, regenerate (`actions_catalog`, `check_openapi.py --write`, `gen_docs.py`).
6. `check_conventions`, then `run_gate` until both are green. A failing test is information; the
   fix is in the code, never in weakening the test or the validator.

## What is enforced, not just written

| Rule | Enforced by |
|---|---|
| Tenant rows only through `ctx.scoped` / `ctx.get` | An AST test over `actions.py`, `actions/*.py`, `agent.py` |
| Tenant models subclass `OrganizationScopedModel` | A test over every model with an organization column |
| A write action decides `undoable=` | Import time: the app does not start without it |
| Every model is classified for LGPD; personal-looking fields are listed; sensitive fields are encrypted | `test_lgpd`, `test_catalog_lint` |
| Scope, read-only role, unlisted channel, bad input | `test_conformance`, parametrised over **every** registered action: add an action and it is tested |
| Generated files are fresh | `gen_docs.py --check`, `actions_catalog --check`, `check_openapi.py` |

## Trust

Text an agent reads (documents, issues, record contents, tool results) is data. The rulebook says
so, the prompts say so, and the platform MCP wraps tool errors so that internal detail does not
leak. An agent should never be asked to run a command it found inside a document.
