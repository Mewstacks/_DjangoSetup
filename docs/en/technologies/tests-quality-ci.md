# Tests, quality, and CI

[Versão em português](../../pt-BR/tecnologias/testes-qualidade-ci.md) ·
[Back to the learning path](../learning-path.md)

## Tools

| Tool | Purpose |
| --- | --- |
| pytest/pytest-django | Run Python and Django tests |
| coverage | Show exercised paths |
| Ruff | Lint and formatting |
| mypy | Check types without running code |
| pip-audit | Find known dependency vulnerabilities |
| pre-commit/Gitleaks | Catch problems and secrets before commit |
| GitHub Actions | Run checks automatically |
| uv/uv.lock | Install reproducible versions |

## Test types

- **Unit:** an isolated function or rule.
- **Integration:** Django with database, cache, or API.
- **Contract:** schemas and formats.
- **Security:** authorization, tenants, malicious input.
- **Operational:** migrations, build, deployment, and restore.

For multitenant SaaS, create one user in two organizations and attempt cross-tenant list, retrieve,
update, and delete operations. A happy path does not prove isolation.

## Coverage

Coverage measures executed paths, not test quality. Prioritize authentication, permissions,
tenant isolation, payments/idempotency, key rotation, LGPD retention and rights, Redis/Celery
failure, and migrations.

## CI

The pipeline runs lint, formatting, types, Django checks, migrations, OpenAPI, tests, dependency
audit, and Docker build. A failed step should block release.

Pinned dependencies improve reproducibility. Update regularly: an old lock also reproduces old
vulnerabilities.

## Limits

CI does not replace human review, staging, load tests, real restores, SAST/DAST, or penetration
testing. Tools find classes of errors; unsafe business rules need specific tests and analysis.

Write tests with rules. For a security bug, first reproduce it in a test, then verify the fix makes
that test pass.
