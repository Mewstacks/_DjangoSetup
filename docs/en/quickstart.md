# Quickstart

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/). Docker is optional.

```bash
uv sync --all-extras
python scripts/bootstrap.py
python manage.py runserver
```

`bootstrap.py` writes `.env` with fresh secrets, migrates (SQLite; `--postgres` for PostgreSQL),
seeds the LGPD purposes, and creates a verified administrator, an organization and an API key. It
prints the credentials once. Interactive API docs: `http://localhost:8000/api/docs/` (development
only). Sign in to the admin at `http://localhost:8000/admin/` (staff need an authenticator in
production; local settings do not ask).

## Call your first action

```bash
python manage.py action list
python manage.py action run notes.create --as admin@example.com --org acme \
  --json '{"title": "Hello"}'
```

The same action over HTTP, with the API key `bootstrap` printed:

```bash
curl -X POST http://localhost:8000/api/v1/actions/notes.create/ \
  -H "Authorization: Bearer $API_KEY" -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" -d '{"title": "Hello"}'
```

## Turn things on

| Capability | Switch |
|---|---|
| Sign-up | `SIGNUP_ENABLED=true` (closed by default) |
| MCP server | `MCP_ENABLED=true` - [guide](guides/mcp.md) |
| OAuth for MCP clients | `OAUTH_ENABLED=true` + `OAUTH_ISSUER_URL` |
| Temporal | `TEMPORAL_ENABLED=true` - `docker compose --profile temporal up` |
| Tracing | `OTEL_ENABLED=true` - `docker compose --profile observability up` |

## Build something

```bash
python manage.py scaffold resource invoices Invoice --fields 'title:str,amount:decimal'
```

Then follow [Start a product](guides/start-a-product.md). If an AI coding agent is helping, point
it at `AGENTS.md` and the development MCP server ([guide](guides/ai-development.md)).

## The quality gate

```bash
python scripts/verify.py      # lint, types, tests, migrations, catalog/OpenAPI/docs drift, deploy check
```

CI runs the same steps, plus PostgreSQL, dependency audit, secret scan, image scan and a weekly
scheduled audit.

Something refuses to start? [Troubleshooting](guides/troubleshooting.md).
