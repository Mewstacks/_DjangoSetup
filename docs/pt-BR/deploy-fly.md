# Deploy no Fly.io

[English version](../en/deployment-fly.md)

## Provisionamento

1. Configure um nome único com `scripts/configure_fly.py`, crie o app e use `gru`.
2. Importe os segredos gerados via stdin. Guarde uma cópia de recuperação das chaves de campo
   em um gerenciador aprovado; o Fly mostrará apenas seus digests.
3. Crie e anexe Fly Managed Postgres em `gru`. O `DATABASE_URL` anexado usa pooling.
4. Crie Upstash Redis em `gru` e use a URL privada em `REDIS_URL`, `CELERY_BROKER_URL` e
   `CELERY_RESULT_BACKEND`.
5. Crie um bucket Tigris privado. Se residência estritamente brasileira for necessária, use um
   provedor S3 compatível no Brasil e configure endpoint, região, bucket e credenciais.
6. Defina `SENTRY_DSN` como Fly Secret e use projetos separados para produção e staging. A
   produção falha ao iniciar quando Sentry está ativo sem DSN.

Variáveis adicionadas pela revisão:

- `HEALTH_READINESS_CACHE_SECONDS=5`: TTL do readiness por worker; `0` desabilita.
- `AXES_LOCKOUT_BY_USERNAME=false`: bloqueio adicional por conta, com risco de lockout abusivo.
- `SESSION_COOKIE_SAMESITE=Lax` e `CSRF_COOKIE_SAMESITE=Lax`: use `None` somente para browser
  cross-site com HTTPS.

## Comportamento do deploy

A imagem roda com UID/GID 10001. Arquivos estáticos recebem fingerprint no build. `fly deploy`
executa `migrate --noinput` uma vez em uma release Machine; falhas abortam a publicação.
Readiness exige PostgreSQL e Redis. Web e worker usam a mesma imagem e escalam separadamente.
Workers Gunicorn são reciclados após cerca de 1.000 requests, com jitter de 100.

Prefira migrations compatíveis com versões anteriores:

1. Adicione estruturas novas ou anuláveis e publique código compatível.
2. Faça backfill assíncrono, limitado e idempotente.
3. Troque leituras/escritas depois de validar métricas.
4. Remova estruturas antigas ou aplique constraints em outro deploy.

Nunca combine migration destrutiva com código que assume sua conclusão.

## Sentry

O SDK remove usuário, body, query string, cookies, credenciais e segredos. Health checks não são
traçados. No painel do Sentry, ative scrubbers, retenção mínima, acesso restrito e alertas para:

- erros novos ou frequentes;
- regressão de taxa de erro ou latência p95;
- tarefas Celery com falha ou fila atrasada;
- regressões após deploy.

Defina `SENTRY_RELEASE` com o commit ou identificador da imagem. Não envie token administrativo
do Sentry para as Machines de runtime.

## Verificação e rollback

```text
fly checks list
fly status
fly logs
fly ssh console -C "python manage.py check --deploy"
```

Valide login/CSRF, isolamento de tenant, solicitação de titular, tarefa Celery, upload assinado e
um erro de teste sem dados pessoais no Sentry. Confirme que body, cookies, e-mail, IP e tokens
não foram enviados.

Rollback da aplicação não desfaz migrations. Reverta código somente quando o schema for
compatível. Em perda ou corrupção, interrompa escritas, preserve evidências, restaure para outro
cluster, valide privadamente, conecte o cluster restaurado e documente as decisões.
