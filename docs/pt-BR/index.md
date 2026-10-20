# Documentação da plataforma

Base Django 6 para sistemas multi-tenant de qualquer tipo. Uma função que você escreve vira
endpoint REST, ferramenta MCP, activity do Temporal e comando de CLI, com autenticação, auditoria
e ferramentas de LGPD já prontas.

| Comece aqui | |
|---|---|
| [Início rápido](quickstart.md) | Rodar localmente e chamar a primeira ação |
| [Arquitetura](architecture.md) | As peças e o caminho de uma requisição |
| [Adicionar uma ação](guides/add-an-action.md) | O caminho de 10 minutos para uma nova capacidade |

## Guias

- [Adicionar um fluxo ou job](guides/add-a-flow.md) - Temporal, ou o motor local quando desligado
- [Servidor MCP](guides/mcp.md) - conectar Claude, Cursor e outros agentes
- [Contas, chaves de API e OAuth](guides/auth.md)
- [Webhooks](guides/webhooks.md), [feature flags e settings](guides/flags-and-settings.md),
  [uploads](guides/uploads.md)
- [Observabilidade](guides/observability.md), [testes](guides/testing.md)

## LGPD

- [Visão geral](lgpd/overview.md) e [matriz de conformidade](lgpd/compliance-matrix.md)

## Segurança

- [Modelo de ameaças](security/threat-model.md), [hardening](security/hardening.md),
  [integridade da auditoria](security/audit-integrity.md), [revisão](security/review.md)

## Deploy

- [Deploy em qualquer lugar](deploy/overview.md), [runbooks](deploy/runbooks.md)
- [Migrando do template da era Celery](migration/from-celery.md)

## Referência (gerada)

[Variáveis de ambiente](reference/env-vars.md) - [Ações e ferramentas MCP](reference/actions.md) -
[Endpoints REST](reference/api.md) - [Motores de fluxo](reference/engines.md) -
[Catálogo de dados pessoais](reference/data-catalog.md) - [Decisões](adr/index.md)
