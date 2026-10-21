## What and why

## Checklist

- [ ] `python scripts/verify.py` passes
- [ ] New model: classified in `<app>/privacy.py` (personal or not, with the reason)
- [ ] New tenant data: `OrganizationScopedModel`, read through `ctx.scoped(...)`
- [ ] New action: docstring, scope, `write`/`destructive`, test for scope, role and cross-tenant
- [ ] Generated files refreshed (`actions_catalog`, `check_openapi.py --write`, `gen_docs.py`)
- [ ] Docs updated in `docs/en` **and** `docs/pt-BR`
- [ ] No secret, personal data or production detail in code, tests, logs or this description
