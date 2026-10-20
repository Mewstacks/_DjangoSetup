# Arquitetura

```
 Cliente ─ REST /api/v1 ─┐
 Agente ── MCP /mcp ─────┤  ActionContext (ator, org, papel, escopos, canal, request id)
 Fluxo ─── Temporal ─────┼─► apps.actions.invoke()
 CLI ───── manage.py ────┘    escopo → papel → rate limit → validação → idempotência
                              → transação → auditoria → journal de undo → log
```

## Apps

| App | Papel |
|---|---|
| `actions` | O kernel: registro `@action`, runtime, adaptadores REST e MCP, journal de undo, ledger de agentes |
| `apikeys`, `oauth`, `accounts` | Credenciais: chaves de API, OAuth 2.1 (PKCE, registro dinâmico), login allauth com MFA |
| `organizations` | Tenants, vínculos, papéis; `OrganizationScopedViewSet`; `OrgScopedPrimaryKeyRelatedField` |
| `flows` | Fluxos e jobs no Temporal ou no motor local; `TemporalTaskBackend` para `django.tasks` |
| `audit` | Trilha de auditoria append-only, com cadeia de hash por organização |
| `privacy` | LGPD: catálogo de dados, consentimento, requisições, retenção, incidentes, RoPA |
| `webhooks`, `flags`, `uploads` | Eventos de saída com outbox, feature flags e settings, arquivos validados |
| `observability` | Pipeline structlog com redação, OpenTelemetry, `doctor`, health |
| `examples` | Notas: recurso de referência completo (remova com o checklist do guia de ações) |

## Regras que o código impõe

- **Uma porta para dados do tenant.** Ações leem linhas só por `ctx.scoped(Model)` / `ctx.get`;
  um teste falha com `Model.objects` em `actions.py`. FKs graváveis usam
  `OrgScopedPrimaryKeyRelatedField`.
- **Negar por padrão para chaves.** Uma chave ou token OAuth age só dentro dos seus escopos; o
  papel do vínculo é lido a cada chamada, nunca copiado para o token.
- **Todo model é classificado.** Um teste falha até cada model ser declarado pessoal ou não em
  `<app>/privacy.py`.
- **Sem segredos em logs.** A redação roda no fim do pipeline de logging, cobrindo também os
  loggers de terceiros.
- **Falha fechado em produção.** `config.settings.production` recusa segredos fracos, banco ou
  Redis sem TLS, hosts curinga e proxy não declarado.

## Módulos de settings

`config.settings.base` (comum), `local` (desenvolvimento), `test`, `production` (estrito, padrão
da imagem). As variáveis estão na [referência gerada](reference/env-vars.md).

## Caminho da requisição em produção

Proxy/ingress (TLS) → gunicorn com workers uvicorn → middleware ASGI `BodyLimit` → middleware
Django (contexto da requisição, allowlist do admin, sessões, CSRF, contexto de organização, CSP)
→ DRF (chave de API, token de sessão ou sessão, permissões de escopo e papel, throttles) →
runtime das ações. O `/mcp` é montado ao lado do Django no app ASGI e usa o mesmo pré-voo.
