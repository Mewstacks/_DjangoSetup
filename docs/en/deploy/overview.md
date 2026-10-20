# Deploy anywhere

One container image, several roles chosen by the first argument:

| Role | Command | Purpose |
|---|---|---|
| `web` (default) | `entrypoint web` | gunicorn + uvicorn workers on `$PORT` |
| `worker` | `entrypoint worker` | Temporal worker (only with `TEMPORAL_ENABLED=true`) |
| `scheduler` | `entrypoint scheduler` | cron-style jobs when Temporal is off; exactly one replica |
| `migrate` | `entrypoint migrate` | `migrate` (+ `flows_sync` with Temporal), then exit |
| `job NAME` | `entrypoint job maintenance.prune_audit` | one job, for cron/CronJob |
| `manage ...` | `entrypoint manage doctor` | any management command |

`DJANGO_SETTINGS_MODULE=config.settings.production` is baked in. Required environment: see
[env vars](../reference/env-vars.md); the strict validators list what is missing. The image runs
as a non-root user and works with a read-only root filesystem (`/tmp` writable).

## Targets

| Where | How |
|---|---|
| Single host | `deploy/compose/compose.prod.yaml`: Caddy (automatic TLS), migrate, web, scheduler, Postgres, Redis, optional `--profile temporal` (server, UI, schema job) and `--profile backup` |
| Kubernetes | `deploy/k8s/base` + `overlays/production` (kustomize): restricted pod security, probes, HPA, PDB, default-deny NetworkPolicy, backup CronJob; run `migrate-job.yaml` before each rollout |
| PaaS (Heroku-style, Dokku, Coolify, Railway, Render) | `Procfile` (release/web/worker/scheduler); provide Postgres and optionally Redis |
| Fly.io, Cloud Run, ECS, Nomad | Run the same image; map `web` to the service and `migrate` to the release/pre-deploy step |
| Bare metal / VM | Install the wheel set from `requirements.txt`, run gunicorn under systemd behind nginx/Caddy; `scheduler` as a second unit |

## Checklist

1. Generate secrets: `python scripts/generate_production_secrets.py`.
2. Declare the proxy (`TRUSTED_PROXY_COUNT=1` behind one load balancer, or CIDRs).
3. Postgres with TLS (or an explicit insecure flag on a private network), Redis with a password.
4. Run `migrate`, then roll `web`. Probes: liveness `/api/v1/health/live/`, readiness
   `/api/v1/health/ready/` (both exempt from the HTTPS redirect).
5. `entrypoint manage doctor --strict` in the pipeline.
6. Uploads and exports: set `S3_BUCKET`, or mount a volume at `/app/media`.
7. Schedule backups ([runbooks](runbooks.md)).

The Compose and Kubernetes manifests render and validate (`docker compose config`,
`kubectl kustomize`); the first image build runs in your CI.
