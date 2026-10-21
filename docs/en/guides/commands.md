# Management commands

Run with `python manage.py <command>` (or `entrypoint manage <command>` in the image). Local-only
commands refuse to run unless `DEV_TOOLS_ALLOWED` is on, which only the local and test settings do.

| Command | What it does |
|---|---|
| `bootstrap` *(local)* | A verified superuser, an organization and an API key, idempotently; prints the credentials once |
| `scaffold resource <app> <Model> --fields ...` *(local)* | Generate a tenant resource that follows the rules; `--dry-run` lists the files |
| `action list` / `action run <name> --as <email> --org <slug> --json '{}'` | The action catalog from the shell; run an action as a person |
| `actions_catalog [--check]` | Write or verify `docs/reference/actions.json` |
| `mcp_config --url ... --org ...` | Print ready-to-paste MCP client configuration (never a secret) |
| `doctor [--strict]` | Is this deployment sound: database, cache, encryption, HTTPS, mail, flows, MCP, audit chain and its privileges, privacy setup |
| `audit_verify [--org ID] [--json] [--expect heads.json]` | Recompute the audit hash chains; record each head, and later prove the newest events were not removed |
| `reencrypt_fields [--dry-run]` | Re-encrypt every encrypted column and the MFA secrets under the active key |
| `privacy_seed [--notice-url URL]` | Baseline purposes and inactive sub-processor stubs |
| `privacy_ropa` | Export the record of processing activities from the catalog |
| `privacy_incident_export REF [--format md]` | Assemble the ANPD incident communication content |
| `retention_sweep [--dry-run]` | Delete or anonymize data past its purpose's retention |
| `flag ...` | Read and set feature flags and settings |
| `flows_sync`, `flows_worker`, `run_scheduler` | Temporal schedules, the Temporal worker, the cron-style scheduler |
| `run_job NAME` / `run_job --due` | Run one job, or whatever is due now |
| `spectacular --file ...` | Generate OpenAPI (see `scripts/check_openapi.py`) |

## Scripts

| Script | Purpose |
|---|---|
| `scripts/bootstrap.py` | `.env`, migrate, seed, administrator, organization, key: first run in one command |
| `scripts/init_project.py --name ...` | Rename the template into your product |
| `scripts/remove_example.py` | Remove the example resource |
| `scripts/verify.py [--fast]` | The quality gate CI runs |
| `scripts/gen_docs.py [--check]` | Reference docs and the AI context files |
| `scripts/check_openapi.py [--write]` | The committed OpenAPI file |
| `scripts/generate_production_secrets.py` | Production secrets, to stdout |
| `scripts/e2e_smoke.py` | Post-deploy smoke test against a running instance |

The development MCP server (`python -m devtools.mcp`) exposes most of this to an AI agent; see
[Building with an AI coding agent](ai-development.md).
