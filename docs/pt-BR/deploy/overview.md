# Deploy em qualquer lugar

Uma imagem de contêiner, vários papéis escolhidos pelo primeiro argumento:

| Papel | Comando | Finalidade |
|---|---|---|
| `web` (padrão) | `entrypoint web` | gunicorn + workers uvicorn em `$PORT` |
| `worker` | `entrypoint worker` | worker do Temporal (só com `TEMPORAL_ENABLED=true`) |
| `scheduler` | `entrypoint scheduler` | jobs agendados quando o Temporal está desligado; exatamente uma réplica |
| `migrate` | `entrypoint migrate` | `migrate` (+ `flows_sync` com Temporal), depois sai |
| `job NOME` | `entrypoint job maintenance.prune_audit` | um job, para cron/CronJob |
| `manage ...` | `entrypoint manage doctor` | qualquer comando de gerenciamento |

`DJANGO_SETTINGS_MODULE=config.settings.production` já vem embutido. Ambiente obrigatório: veja as
[variáveis](../reference/env-vars.md); os validadores estritos dizem o que falta. A imagem roda
como usuário não-root e funciona com sistema de arquivos raiz somente leitura (`/tmp` gravável).

## Destinos

| Onde | Como |
|---|---|
| Um único host | `deploy/compose/compose.prod.yaml`: Caddy (TLS automático), migrate, web, scheduler, Postgres, Redis, opcionais `--profile temporal` (servidor, UI, job de schema) e `--profile backup` |
| Kubernetes | `deploy/k8s/base` + `overlays/production` (kustomize): pod security restrito, probes, HPA, PDB, NetworkPolicy default-deny, CronJob de backup; rode `migrate-job.yaml` antes de cada rollout |
| PaaS (estilo Heroku, Dokku, Coolify, Railway, Render) | `Procfile` (release/web/worker/scheduler); forneça Postgres e, opcionalmente, Redis |
| Fly.io, Cloud Run, ECS, Nomad | Rode a mesma imagem; mapeie `web` para o serviço e `migrate` para a etapa de release/pré-deploy |
| Bare metal / VM | Instale as dependências de `requirements.txt`, rode o gunicorn em systemd atrás de nginx/Caddy; `scheduler` como segunda unit |

## Checklist

1. Gere os segredos: `python scripts/generate_production_secrets.py`.
2. Declare o proxy (`TRUSTED_PROXY_COUNT=1` atrás de um load balancer, ou CIDRs).
3. Postgres com TLS (ou flag explícita de transporte inseguro em rede privada), Redis com senha.
4. Rode `migrate`, depois o rollout do `web`. Probes: liveness `/api/v1/health/live/`, readiness
   `/api/v1/health/ready/` (ambos isentos do redirect HTTPS).
5. `entrypoint manage doctor --strict` no pipeline.
6. Uploads e exportações: defina `S3_BUCKET`, ou monte um volume em `/app/media`.
7. Agende backups ([runbooks](runbooks.md)).

Os manifestos de Compose e Kubernetes renderizam e validam (`docker compose config`,
`kubectl kustomize`); o primeiro build da imagem roda no seu CI.
