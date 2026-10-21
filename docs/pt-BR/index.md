# Documentação da plataforma

Uma base Django 6 para sistemas multi-tenant de qualquer tipo. Uma função que você escreve vira
endpoint REST, ferramenta MCP, atividade Temporal e comando de CLI, com autenticação, auditoria e
ferramentas de proteção de dados (LGPD) já no lugar, e um livro de regras que uma pessoa engenheira ou
um agente de IA consegue seguir.

| Comece aqui | |
|---|---|
| [Início rápido](quickstart.md) | Rode localmente e chame sua primeira ação |
| [Comece um produto](guides/start-a-product.md) | De um clone a um produto publicado, em ordem |
| [Construindo com um agente de IA](guides/ai-development.md) | `AGENTS.md`, o servidor MCP de desenvolvimento, o scaffold |
| [Arquitetura](architecture.md) | As peças e como uma requisição passa por elas |
| [Adicionar uma ação](guides/add-an-action.md) | O caminho de 10 minutos para uma nova capacidade |

## Guias

- [Adicionar um flow ou job](guides/add-a-flow.md) - Temporal, ou o motor local quando desligado
- [Servidor MCP](guides/mcp.md) - conecte Claude, Cursor e outros agentes a um produto em execução
- [Contas, chaves de API e OAuth](guides/auth.md), [papéis e permissões](guides/roles-and-permissions.md)
- [Frontend e integração com SPA](guides/frontend.md), [convenções da API](guides/api-conventions.md)
- [Webhooks](guides/webhooks.md), [feature flags e configurações](guides/flags-and-settings.md),
  [uploads](guides/uploads.md), [e-mail e idiomas](guides/email-and-i18n.md)
- [Cobrança e planos](guides/billing.md), [encerrando um tenant](guides/offboarding.md)
- [Observabilidade](guides/observability.md), [testes](guides/testing.md),
  [comandos de gerenciamento](guides/commands.md), [solução de problemas](guides/troubleshooting.md)
- [Atualizando a partir do upstream](guides/upgrading.md)

## LGPD

- [Visão geral](lgpd/overview.md), [matriz de conformidade](lgpd/compliance-matrix.md) e
  [modelos de documentos](lgpd/templates.md)

## Segurança

- [Modelo de ameaças](security/threat-model.md), [hardening](security/hardening.md),
  [integridade da auditoria](security/audit-integrity.md), [revisão](security/review.md),
  [checklist de quem constrói](security/builder-checklist.md)

## Implantação

- [Implante em qualquer lugar](deploy/overview.md), [runbooks](deploy/runbooks.md)
- [Atualizando do template da era Celery](migration/from-celery.md)

## Referência (gerada)

[Variáveis de ambiente](reference/env-vars.md) - [Ações e ferramentas MCP](reference/actions.md) -
[Endpoints REST](reference/api.md) - [Motores de flow](reference/engines.md) -
[Catálogo de dados pessoais](reference/data-catalog.md) - [Decisões](adr/index.md)

Para agentes de IA: `AGENTS.md` e `llms.txt` na raiz do repositório.
