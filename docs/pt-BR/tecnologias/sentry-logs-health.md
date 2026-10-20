# Sentry, logs e health checks

[English version](../../en/technologies/sentry-logs-health.md) ·
[Voltar à trilha](../trilha-aprendizado.md)

## Observabilidade

Observabilidade é conseguir responder: “o que falhou, para quem, quando e em qual versão?”

- **Logs:** eventos escritos pela aplicação.
- **Sentry:** agrupa exceções, stack traces e performance.
- **Métricas:** números ao longo do tempo, como latência e erros.
- **Request ID:** liga uma resposta às linhas de log e ao evento do Sentry.

## Logs estruturados

O projeto usa JSON porque máquinas conseguem pesquisar campos como nível, request ID e
organization ID. Não registre bodies, cookies, tokens, senhas ou dados pessoais.

Auditoria e log não são iguais. Log ajuda operação; auditoria registra uma ação de negócio
controlada e imutável.

## Sentry com minimização

O SDK está configurado sem PII padrão, bodies, variáveis locais e contexto de código. Filtros
removem campos sensíveis antes do envio.

Mesmo assim:

- configure scrubbers no painel Sentry;
- use retenção mínima;
- restrinja membros e exija MFA;
- separe projetos/ambientes;
- teste redaction com dados sintéticos.

Sentry é um fornecedor que precisa entrar no inventário LGPD.

## Liveness e readiness

```text
/health/live/  → o processo responde?
/health/ready/ → PostgreSQL e Redis funcionam?
```

Fly usa health checks para evitar tráfego em instâncias não prontas. Readiness possui cache curto
por worker para não virar uma forma barata de sobrecarregar dependências.

Health check não substitui alerta. Um sistema pode responder `200` e estar lento, sem worker ou
com fila crescendo.

## O que monitorar?

Taxa de erros, latência p95/p99, deploy/release, conexões do banco, memória Redis, idade da fila,
falhas de task, espaço do storage e login bloqueado. Alertas devem ter responsável e ação descrita
em runbook; alerta ignorado é apenas ruído.
