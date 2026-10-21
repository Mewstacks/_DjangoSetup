# Testing

```bash
python -m pytest                       # sqlite, in-memory storage
TEST_USE_EXTERNAL_SERVICES=true DB_ENGINE=postgresql DB_HOST=127.0.0.1 DB_NAME=saas DB_USER=saas \
  DB_PASSWORD=... python -m pytest     # PostgreSQL (+ REDIS_URL), as CI does
python scripts/verify.py --fast        # lint, format, tests, drift checks
python scripts/verify.py               # adds mypy (strict) and the production deploy check
```

The PostgreSQL run matters: the audit trigger, the owner-only prune function, the role separation
and the `CHECK` constraint exist only there, and their tests are skipped on SQLite. CI runs both.

Fixtures: `user` (verified e-mail), `organization`, `membership`, `org_client` (logged in and
scoped), `other_org_client` (a second tenant, for isolation tests).

## What the suite guards, by name

- `test_security_regressions`, `test_hardening`, `test_abuse_limits`, `test_web_hardening`,
  `test_key_rotation`, `test_netguard`, `test_body_timeout`, `test_export_link` - one test per
  review finding (see [the review](../security/review.md)).
- `test_conformance` - properties of **every registered action**: scope, read-only role, unlisted
  channel, bad input never echoed, undo decision, no secret-named output. A new action is covered
  without writing a test.
- `test_tenancy_structure`, `test_tenant_isolation` - tenant models, the AST door, undo across
  tenants, quotas.
- `test_catalog_lint`, `test_lgpd`, `test_lgpd_retention`, `test_lgpd_extras`, `test_privacy` -
  classification, listed personal fields, encrypted sensitive data, erasure, retention, incidents.
- `test_actions`, `test_mcp`, `test_mcp_protocol`, `test_apikeys`, `test_oauth` - runtime, API/MCP
  parity, protocol revisions, auth matrix.
- `test_flows`, `test_flows_temporal` - both engines; Temporal against the SDK test server
  (downloaded on first use; mark `temporal`).
- `test_audit_integrity` - keyed chain, head check, and (PostgreSQL) trigger and role separation.
- `test_scaffold` - the scaffold writes code that passes its own tests, lint and formatter (it
  copies the project; mark `slow_scaffold`, about 10 seconds).
- `test_devtools`, `test_bootstrap` - the AI context files are fresh, the development MCP server
  answers over the protocol, first-run scripts.
- `test_docs` - both languages have the same pages and the same structure; links resolve.

Drift checks: action catalog (`docs/reference/actions.json`), OpenAPI (`openapi-schema.yml`),
generated reference docs and agent files (`gen_docs.py --check`) - regenerate with the commands in
the [add-an-action guide](add-an-action.md).
