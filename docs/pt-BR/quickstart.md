# Início rápido

Requisitos: Python 3.12+, [uv](https://docs.astral.sh/uv/). Docker é opcional.

```bash
uv sync --all-extras
python scripts/init_local.py --sqlite      # grava o .env com segredos locais novos
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Documentação interativa da API: `http://localhost:8000/api/docs/` (somente em desenvolvimento).

## Chame a primeira ação

```bash
python manage.py action list
python manage.py action run notes.create --as voce@example.com --org acme \
  --json '{"title": "Olá"}'
```

A mesma ação por HTTP, com chave de API (criada no app, exibida uma vez):

```bash
curl -X POST http://localhost:8000/api/v1/actions/notes.create/ \
  -H "Authorization: Bearer $API_KEY" -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" -d '{"title": "Olá"}'
```

## Ligue o que precisar

| Capacidade | Chave |
|---|---|
| Cadastro | `SIGNUP_ENABLED=true` (fechado por padrão) |
| Servidor MCP | `MCP_ENABLED=true` - [guia](guides/mcp.md) |
| OAuth para clientes MCP | `OAUTH_ENABLED=true` + `OAUTH_ISSUER_URL` |
| Temporal | `TEMPORAL_ENABLED=true` - `docker compose --profile temporal up` |
| Tracing | `OTEL_ENABLED=true` - `docker compose --profile observability up` |

## O gate de qualidade

```bash
python scripts/verify.py      # lint, tipos, testes, migrations, drift de catálogo/OpenAPI/docs, deploy check
```

O CI roda os mesmos passos, mais PostgreSQL, auditoria de dependências, varredura de segredos e
da imagem.
