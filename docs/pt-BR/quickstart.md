# Início rápido

Requisitos: Python 3.12+, [uv](https://docs.astral.sh/uv/). Docker é opcional.

```bash
uv sync --all-extras
python scripts/bootstrap.py
python manage.py runserver
```

O `bootstrap.py` escreve o `.env` com segredos novos, migra (SQLite; `--postgres` para PostgreSQL),
semeia as finalidades da LGPD e cria um administrador verificado, uma organização e uma chave de API.
Imprime as credenciais uma vez. Docs interativas da API: `http://localhost:8000/api/docs/` (só em
desenvolvimento). Entre no admin em `http://localhost:8000/admin/` (em produção staff precisa de um
autenticador; as configurações locais não pedem).

## Chame sua primeira ação

```bash
python manage.py action list
python manage.py action run notes.create --as admin@example.com --org acme \
  --json '{"title": "Olá"}'
```

A mesma ação por HTTP, com a chave de API que o `bootstrap` imprimiu:

```bash
curl -X POST http://localhost:8000/api/v1/actions/notes.create/ \
  -H "Authorization: Bearer $API_KEY" -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" -d '{"title": "Olá"}'
```

## Ligue as coisas

| Capacidade | Chave |
|---|---|
| Cadastro | `SIGNUP_ENABLED=true` (fechado por padrão) |
| Servidor MCP | `MCP_ENABLED=true` - [guia](guides/mcp.md) |
| OAuth para clientes MCP | `OAUTH_ENABLED=true` + `OAUTH_ISSUER_URL` |
| Temporal | `TEMPORAL_ENABLED=true` - `docker compose --profile temporal up` |
| Tracing | `OTEL_ENABLED=true` - `docker compose --profile observability up` |

## Construa algo

```bash
python manage.py scaffold resource invoices Invoice --fields 'title:str,amount:decimal'
```

Depois siga [Comece um produto](guides/start-a-product.md). Se um agente de IA estiver ajudando,
aponte-o para o `AGENTS.md` e para o servidor MCP de desenvolvimento ([guia](guides/ai-development.md)).

## O gate de qualidade

```bash
python scripts/verify.py      # lint, tipos, testes, migrações, drift de catálogo/OpenAPI/docs, checagem de deploy
```

O CI roda os mesmos passos, mais PostgreSQL, auditoria de dependências, varredura de segredos,
varredura de imagem e uma auditoria semanal agendada.

Algo se recusa a iniciar? [Solução de problemas](guides/troubleshooting.md).
