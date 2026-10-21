# Arquitetura

```
 Cliente ─ REST /api/v1 ─┐
 Agente ── MCP /mcp ─────┤  ActionContext (ator, organização, papel, escopos, canal, request id)
 Flow ──── Temporal ─────┼─► apps.actions.invoke()
 CLI ───── manage.py ────┘    escopo → papel → rate limit → validação → idempotência
                              → transação → auditoria → diário de desfazer → log
```

## Apps

| App | Papel |
|---|---|
| `actions` | O núcleo: registro `@action`, runtime, adaptadores REST e MCP, diário de desfazer, livro de execuções de agentes |
| `apikeys`, `oauth`, `accounts` | Credenciais: chaves de API, OAuth 2.1 (PKCE, política de registro), login com allauth e MFA, MFA de staff, revogação de chaves na redefinição |
| `organizations` | Tenants, vínculos, papéis, cotas; `OrganizationScopedViewSet`; `OrgScopedPrimaryKeyRelatedField` |
| `flows` | Flows e jobs no Temporal ou no motor local; `TemporalTaskBackend` para `django.tasks` |
| `audit` | Trilha de auditoria somente de acréscimo, com cadeia de hash chaveada por organização |
| `privacy` | LGPD: catálogo de dados, consentimento, consentimento de cookies, solicitações, retenção, incidentes, relatórios de impacto, ponto de encaixe de verificação de idade, RoPA |
| `webhooks`, `flags`, `uploads` | Eventos de saída com outbox, feature flags e configurações, arquivos validados |
| `observability` | Pipeline structlog com redação, OpenTelemetry, `doctor`, health |
| `common` | Criptografia, guarda de rede, logging, middleware, limites de taxa |
| `examples` | Notes: um recurso de referência completo (remova com `scripts/remove_example.py`) |
| `devtools` (não é um app) | O livro de regras, scaffold, checagens de convenção e o servidor MCP de desenvolvimento: [guia de IA](guides/ai-development.md) |

## Regras que o código impõe

- **Uma porta para os dados do tenant.** Ações leem linhas só por `ctx.scoped(Model)` / `ctx.get`; um
  teste falha com `Model.objects` em `actions.py`, `actions/*.py` e `agent.py`, e outro com um modelo
  que tem coluna de organização e não é escopado nem explicado. FKs graváveis usam
  `OrgScopedPrimaryKeyRelatedField`.
- **Default deny para chaves.** Uma chave ou token OAuth age só dentro dos seus escopos; o papel do
  vínculo é lido a cada chamada, nunca copiado para um token.
- **Todo modelo é classificado.** Um teste falha até cada modelo ser declarado pessoal ou não em
  `<app>/privacy.py`; outro quando um campo de cara pessoal não está listado ou um dado sensível não é
  cifrado.
- **Uma ação de escrita decide o desfazer.** O app não inicia até ela dizer `undoable=True` ou por quê.
- **Sem segredos em logs.** A redação roda no fim do pipeline de logs, então loggers de terceiros também
  são cobertos.
- **Falha fechada em produção.** `config.settings.production` recusa segredos fracos, TLS de banco sem
  verificação, Redis em texto simples, hosts com curinga, proxy não declarado e controlador ou DPO
  ausentes.
- **A trilha de auditoria resiste à própria aplicação.** Cadeia chaveada, poda só do dono, papel de
  runtime que não consegue reescrevê-la ([ADR 13](adr/audit-chain-and-role-split.md)).
- **As regras são checadas para toda ação.** A suíte de conformidade é parametrizada sobre o registro,
  então uma ação nova é testada sem escrever teste.

## Módulos de configuração

`config.settings.base` (compartilhado), `local` (desenvolvimento), `test`, `production` (estrito, o
padrão da imagem). As variáveis estão na [referência gerada](reference/env-vars.md).

## Caminho da requisição em produção

Proxy/ingress (TLS) → gunicorn com workers uvicorn → middleware ASGI `BodyLimit` (tamanho e tempo de
leitura) → middleware do Django (cabeçalhos de segurança, contexto da requisição, allowlist do admin,
no-store, sessões, CSRF, MFA de staff, contexto da organização, CSP) → DRF (chave de API, token de
sessão ou sessão, permissões de escopo e papel, limites de taxa) → runtime de ações. O `/mcp` é montado
ao lado do Django no app ASGI e compartilha as mesmas checagens de pré-voo.

## Dois servidores MCP

`/mcp` deixa um agente operar um produto em execução como uma pessoa. `python -m devtools.mcp` deixa um
agente construir o produto. Compartilham os registros, mais nada ([ADR 15](adr/two-mcp-servers.md)).
