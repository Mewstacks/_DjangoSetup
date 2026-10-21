# Implante em qualquer lugar

Uma imagem de contêiner, vários papéis escolhidos pelo primeiro argumento:

| Papel | Comando | Finalidade |
|---|---|---|
| `web` (padrão) | `entrypoint web` | gunicorn + workers uvicorn em `$PORT` |
| `worker` | `entrypoint worker` | worker do Temporal (só com `TEMPORAL_ENABLED=true`) |
| `scheduler` | `entrypoint scheduler` | jobs estilo cron quando o Temporal está desligado; exatamente uma réplica |
| `migrate` | `entrypoint migrate` | `migrate` (+ `flows_sync` com Temporal), depois sai |
| `job NOME` | `entrypoint job maintenance.prune_audit` | um job, para cron/CronJob |
| `manage ...` | `entrypoint manage doctor` | qualquer comando de gerenciamento |

`DJANGO_SETTINGS_MODULE=config.settings.production` já vem embutido. O ambiente mínimo está em
[Solução de problemas](../guides/troubleshooting.md); os validadores estritos nomeiam o que falta, e
[variáveis de ambiente](../reference/env-vars.md) lista tudo. A imagem roda como usuário sem
privilégios e funciona com sistema de arquivos raiz somente leitura (`/tmp` gravável). Construa com
`--build-arg EXTRAS="--extra otel"` se quiser o OpenTelemetry na imagem.

## Alvos

| Onde | Como |
|---|---|
| Host único | `deploy/compose/compose.prod.yaml`: Caddy (TLS automático), migrate, web, scheduler, Postgres, Redis, opcionais `--profile temporal` (servidor, UI, job de schema) e `--profile backup` |
| Kubernetes | `deploy/k8s/base` + `overlays/production` (kustomize): pod security restrita, probes, HPA, PDB, NetworkPolicy default-deny com saída só para a internet pública, CronJob de backup; rode `migrate-job.yaml` antes de cada rollout |
| Qualquer PaaS com Procfile | `Procfile` (release/web/worker/scheduler); forneça Postgres e opcionalmente Redis |
| Cloud Run, ECS, Nomad, outro PaaS | Rode a mesma imagem; mapeie `web` para o serviço e `migrate` para o passo de release/pré-deploy |
| Bare metal / VM | Instale o conjunto de wheels de `requirements.txt`, rode o gunicorn sob systemd atrás de nginx/Caddy; `scheduler` como segunda unidade |

## Duas identidades de banco

O dono do schema roda as migrações; a aplicação conecta com um papel que não é dono de nada. Essa
separação é o que torna a trilha de auditoria resistente a um processo web comprometido
([ADR 13](../adr/audit-chain-and-role-split.md)).

- Compose: `DB_USER` (dono) é usado só por `migrate` e Temporal; web, scheduler e worker usam
  `APP_DB_USER` / `APP_DB_PASSWORD`. O papel é criado na primeira partida por
  `deploy/compose/initdb/10-runtime-role.sh`.
- Kubernetes: `app-secrets` guarda o papel de runtime (`DB_USER`/`DB_PASSWORD`); o Job `migrate` lê o
  dono do secret `app-migrator` e recebe `AUDIT_RUNTIME_ROLE`.
- Em outros lugares: crie o papel você mesmo, conceda `SELECT, INSERT, UPDATE, DELETE` nas tabelas e
  `USAGE, SELECT` nas sequências (privilégios padrão para o que o dono criar depois), e defina
  `AUDIT_RUNTIME_ROLE` com o nome dele ao rodar `migrate`.

O `manage.py doctor` avisa quando o papel de runtime ainda consegue reescrever a trilha.

## Checklist

1. Gere os segredos: `python scripts/generate_production_secrets.py`.
2. Declare o proxy (`TRUSTED_PROXY_COUNT=1` atrás de um balanceador, ou CIDRs) e `PUBLIC_URL`.
3. Postgres com TLS verificado (`sslmode=verify-full`), Redis sobre `rediss://`; numa rede privada que
   você controla, `DB_ALLOW_INSECURE_TRANSPORT` / `REDIS_ALLOW_INSECURE` explícitos registram essa
   decisão.
4. Rode `migrate`, depois o rollout do `web`. Probes: liveness `/api/v1/health/live/`, readiness
   `/api/v1/health/ready/` (ambos isentos do redirecionamento HTTPS).
5. `entrypoint manage doctor --strict` no pipeline.
6. Uploads e exportações: defina `S3_BUCKET`, ou monte um volume em `/app/media` com
   `OBJECT_STORAGE_REQUIRED=false`.
7. Defina o controlador e o DPO (`PRIVACY_CONTROLLER_NAME`, `DPO_EMAIL`): a produção se recusa a
   iniciar sem eles.
8. Agende backups ([runbooks](runbooks.md)); guarde-os cifrados.
9. Envie as linhas de cabeça da auditoria (eventos de log `audit_head`) a um sistema que o banco não
   alcance.

## Publicando

Crie a tag `vX.Y.Z`. O workflow de release roda o gate completo do CI, constrói a imagem, a escaneia
(Trivy), a assina (cosign, sem chave), anexa proveniência e um SBOM como atestados OCI e cria um GitHub
Release que cita o **digest** da imagem. Implante pelo digest (`imagem@sha256:...`), no overlay do
Kubernetes e no Job de migração: uma tag pode ser movida, um digest não. O CI também renderiza o
arquivo Compose e o overlay kustomize, escaneia os manifestos atrás de configurações erradas e sobe a
imagem construída com as configurações de produção.
