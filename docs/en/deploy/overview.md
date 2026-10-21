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

`DJANGO_SETTINGS_MODULE=config.settings.production` is baked in. The minimum environment is in
[Troubleshooting](../guides/troubleshooting.md); the strict validators name what is missing, and
[env vars](../reference/env-vars.md) lists everything. The image runs as a non-root user and works
with a read-only root filesystem (`/tmp` writable). Build with
`--build-arg EXTRAS="--extra otel"` if you want OpenTelemetry in the image.

## Targets

| Where | How |
|---|---|
| Single host | `deploy/compose/compose.prod.yaml`: Caddy (automatic TLS), migrate, web, scheduler, Postgres, Redis, optional `--profile temporal` (server, UI, schema job) and `--profile backup` |
| Kubernetes | `deploy/k8s/base` + `overlays/production` (kustomize): restricted pod security, probes, HPA, PDB, default-deny NetworkPolicy with public-internet-only egress, backup CronJob; run `migrate-job.yaml` before each rollout |
| PaaS (Heroku-style, Dokku, Coolify, Railway, Render) | `Procfile` (release/web/worker/scheduler); provide Postgres and optionally Redis |
| Cloud Run, ECS, Nomad, any other PaaS | Run the same image; map `web` to the service and `migrate` to the release/pre-deploy step |
| Bare metal / VM | Install the wheel set from `requirements.txt`, run gunicorn under systemd behind nginx/Caddy; `scheduler` as a second unit |

## Two database identities

The schema owner runs migrations; the application connects as a role that owns nothing. That
separation is what makes the audit trail resistant to a compromised web process
([ADR 13](../adr/audit-chain-and-role-split.md)).

- Compose: `DB_USER` (owner) is used by `migrate` and Temporal only; web, scheduler and worker use
  `APP_DB_USER` / `APP_DB_PASSWORD`. The role is created on first start by
  `deploy/compose/initdb/10-runtime-role.sh`.
- Kubernetes: `app-secrets` holds the runtime role (`DB_USER`/`DB_PASSWORD`); the `migrate` Job reads
  the owner from the `app-migrator` secret and receives `AUDIT_RUNTIME_ROLE`.
- Elsewhere: create the role yourself, grant it `SELECT, INSERT, UPDATE, DELETE` on tables and
  `USAGE, SELECT` on sequences (default privileges for what the owner creates later), and set
  `AUDIT_RUNTIME_ROLE` to its name when you run `migrate`.

`manage.py doctor` reports when the runtime role can still rewrite the trail.

## Checklist

1. Generate secrets: `python scripts/generate_production_secrets.py`.
2. Declare the proxy (`TRUSTED_PROXY_COUNT=1` behind one load balancer, or CIDRs) and `PUBLIC_URL`.
3. Postgres with verified TLS (`sslmode=verify-full`), Redis over `rediss://`; on a private network
   you control, the explicit `DB_ALLOW_INSECURE_TRANSPORT` / `REDIS_ALLOW_INSECURE` record that
   decision.
4. Run `migrate`, then roll `web`. Probes: liveness `/api/v1/health/live/`, readiness
   `/api/v1/health/ready/` (both exempt from the HTTPS redirect).
5. `entrypoint manage doctor --strict` in the pipeline.
6. Uploads and exports: set `S3_BUCKET`, or mount a volume at `/app/media` with
   `OBJECT_STORAGE_REQUIRED=false`.
7. Set the controller and DPO (`PRIVACY_CONTROLLER_NAME`, `DPO_EMAIL`): production refuses to start
   without them.
8. Schedule backups ([runbooks](runbooks.md)); store them encrypted.
9. Ship the audit head lines (`audit_head` log events) to a system the database cannot reach.

## Releasing

Tag `vX.Y.Z`. The release workflow runs the full CI gate, builds the image, scans it (Trivy), signs it
(cosign, keyless), attaches provenance and an SBOM as OCI attestations and creates a GitHub
Release naming the image **digest**. Deploy by digest (`image@sha256:...`), in the Kubernetes
overlay and the migrate Job alike: a tag can be moved, a digest cannot. CI also renders the Compose
file and the kustomize overlay, scans the manifests for misconfiguration and boots the built image
with production settings.
