# Testes

```bash
python -m pytest                       # sqlite, armazenamento em memória
TEST_USE_EXTERNAL_SERVICES=true python -m pytest   # PostgreSQL + Redis, como o CI
python scripts/verify.py               # tudo que o gate do CI roda
```

Fixtures: `user` (e-mail verificado), `organization`, `membership`, `org_client` (logado e com
organização), `other_org_client` (segundo tenant, para testes de isolamento).

O que a suíte protege, por nome:

- `test_security_regressions` - um teste por achado de auditoria.
- `test_actions`, `test_mcp`, `test_apikeys`, `test_oauth` - runtime, paridade API/MCP, matriz
  de auth.
- `test_flows`, `test_flows_temporal` - os dois motores; Temporal contra o servidor de teste do
  SDK (baixado no primeiro uso; marca `temporal`).
- `test_audit_integrity` - cadeia e trigger (só PostgreSQL).
- `test_lgpd` - todo model classificado, cadeia de consentimento, requisições, retenção.
- `test_uploads`, `test_webhooks`, `test_flags`, `test_scheduler`, `test_accounts_flow`.

Checagens de drift: catálogo de ações (`docs/reference/actions.json`), OpenAPI
(`openapi-schema.yml`), docs de referência geradas - regenere com os comandos do guia de ações.
