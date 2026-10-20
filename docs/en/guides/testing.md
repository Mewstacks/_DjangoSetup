# Testing

```bash
python -m pytest                       # sqlite, in-memory storage
TEST_USE_EXTERNAL_SERVICES=true python -m pytest   # PostgreSQL + Redis, as CI does
python scripts/verify.py               # everything CI's gate runs
```

Fixtures: `user` (verified e-mail), `organization`, `membership`, `org_client` (logged in and
scoped), `other_org_client` (a second tenant, for isolation tests).

What the suite guards, by name:

- `test_security_regressions` - one test per audit finding.
- `test_actions`, `test_mcp`, `test_apikeys`, `test_oauth` - runtime, parity API/MCP, auth matrix.
- `test_flows`, `test_flows_temporal` - both engines; Temporal against the SDK test server
  (downloaded on first use; mark `temporal`).
- `test_audit_integrity` - chain and trigger (PostgreSQL only).
- `test_lgpd` - every model classified, consent chain, requests, retention.
- `test_uploads`, `test_webhooks`, `test_flags`, `test_scheduler`, `test_accounts_flow`.

Drift checks: action catalog (`docs/reference/actions.json`), OpenAPI (`openapi-schema.yml`),
generated reference docs - regenerate with the commands in the add-an-action guide.
