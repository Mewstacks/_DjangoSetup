# Arquitetura

[English version](../en/architecture.md)

O starter é um monólito modular. Isso é intencional: transações de banco, operações de
privacidade, migrations e autorização permanecem compreensíveis enquanto os processos web e
worker escalam horizontalmente. Separe serviços somente quando as métricas mostrarem uma
fronteira real.

## Runtime

- `web`: instâncias Django ASGI sem estado atrás do Fly Proxy. Sessões, throttling e cache ficam
  no Redis; dados persistentes ficam no PostgreSQL ou em object storage privado.
- `worker`: consumidores Celery usando a mesma imagem e código. Tarefas devem ser idempotentes,
  usar retentativas com backoff limitado e receber IDs, não dados pessoais.
- PostgreSQL gerenciado: fonte principal dos dados, conexões agrupadas, alta disponibilidade,
  backups e criptografia em trânsito e repouso.
- Redis: cache, sessões, bloqueios de autenticação, throttling e broker. Nunca é a fonte
  principal de registros de negócio ou privacidade.
- Object storage privado: uploads e exportações por URLs assinadas de curta duração.
- Sentry e logs JSON: telemetria com dados pessoais removidos e request IDs para correlação.

O endpoint público de readiness memoriza o resultado por worker por cinco segundos, reduzindo
carga no PostgreSQL/Redis sem depender do Redis para aplicar throttle.

## Limites da aplicação

- `accounts`: identidade. OIDC e passkeys devem ser adicionados aqui.
- `organizations`: tenant opcional, associações, papéis, middleware e
  `OrganizationScopedModel`.
- `privacy`: finalidades, avisos, consentimentos, solicitações de titulares e incidentes.
- `audit`: eventos imutáveis; metadados com dados pessoais ou segredos são rejeitados.
- `common`: criptografia, contexto da requisição, erros, health checks, logs e limpeza do Sentry.

## Invariante de tenant

O UUID enviado pelo cliente é apenas um seletor. O middleware confirma a associação ativa do
usuário e retorna `404` em caso de falha. Endpoints de produto devem exigir o contexto e limitar
leituras e escritas a `request.organization`.

A listagem de organizações busca o papel atual por subquery/annotation, sem carregar todos os
membros. A quantidade de queries permanece limitada mesmo quando a organização cresce.

Para produtos de alto risco, adicione Row-Level Security do PostgreSQL como segunda camada
depois que o schema estiver definido. Políticas genéricas podem quebrar jobs e migrations.

## Caminho de escala

1. Aumente Machines web e worker separadamente; mantenha PostgreSQL e Redis em `gru`.
2. Meça p95, queries, fila, CPU/conexões do banco e taxa de erros.
3. Crie índices a partir de planos reais; cacheie somente dados derivados não sensíveis.
4. Adicione réplicas ou outras regiões apenas após projetar consistência e transferências
   internacionais.
5. Extraia serviços apenas quando houver fronteira independente de escala, propriedade ou falha.
