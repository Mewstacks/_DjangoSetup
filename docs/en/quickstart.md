# Quickstart

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/). Docker is optional.

```bash
uv sync --all-extras
python scripts/init_local.py --sqlite      # writes .env with fresh local secrets
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Interactive API docs: `http://localhost:8000/api/docs/` (development only).

## Call your first action

```bash
python manage.py action list
python manage.py action run notes.create --as you@example.com --org acme \
  --json '{"title": "Hello"}'
```

The same action over HTTP, with an API key (create one in the app, shown once):

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

## The quality gate

```bash
python scripts/verify.py      # lint, types, tests, migrations, catalog/OpenAPI/docs drift, deploy check
```

CI runs the same steps, plus PostgreSQL, dependency audit, secret scan and image scan.
