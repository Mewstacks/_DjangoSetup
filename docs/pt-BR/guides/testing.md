# Testes

```bash
python -m pytest                       # sqlite, armazenamento em memória
TEST_USE_EXTERNAL_SERVICES=true DB_ENGINE=postgresql DB_HOST=127.0.0.1 DB_NAME=saas DB_USER=saas \
  DB_PASSWORD=... python -m pytest     # PostgreSQL (+ REDIS_URL), como o CI faz
python scripts/verify.py --fast        # lint, formato, testes, checagens de drift
python scripts/verify.py               # acrescenta mypy (strict) e a checagem de deploy de produção
```

A execução com PostgreSQL importa: o trigger de auditoria, a função de poda só do dono, a separação de
papéis e a constraint `CHECK` só existem lá, e seus testes são pulados no SQLite. O CI roda os dois.

Fixtures: `user` (e-mail verificado), `organization`, `membership`, `org_client` (logado e
escopado), `other_org_client` (um segundo tenant, para testes de isolamento).

## O que a suíte protege, por nome

- `test_security_regressions`, `test_hardening`, `test_abuse_limits`, `test_web_hardening`,
  `test_key_rotation`, `test_netguard`, `test_body_timeout`, `test_export_link` - um teste por
  achado de revisão (veja [a revisão](../security/review.md)).
- `test_conformance` - propriedades de **toda ação registrada**: escopo, papel somente leitura, canal
  não listado, entrada inválida nunca repetida, decisão de desfazer, saída sem nome de segredo. Uma
  ação nova é coberta sem escrever teste.
- `test_tenancy_structure`, `test_tenant_isolation` - modelos de tenant, a porta de AST, desfazer entre
  tenants, cotas.
- `test_catalog_lint`, `test_lgpd`, `test_lgpd_retention`, `test_lgpd_extras`, `test_privacy` -
  classificação, campos pessoais listados, dados sensíveis cifrados, eliminação, retenção, incidentes.
- `test_actions`, `test_mcp`, `test_mcp_protocol`, `test_apikeys`, `test_oauth` - runtime, paridade
  API/MCP, revisões do protocolo, matriz de autenticação.
- `test_flows`, `test_flows_temporal` - os dois motores; Temporal contra o servidor de teste do SDK
  (baixado no primeiro uso; marca `temporal`).
- `test_audit_integrity` - cadeia chaveada, checagem de cabeça e (PostgreSQL) trigger e separação de
  papéis.
- `test_scaffold` - o scaffold escreve código que passa nos próprios testes, no lint e no formatador
  (copia o projeto; marca `slow_scaffold`, cerca de 10 segundos).
- `test_devtools`, `test_bootstrap` - os arquivos de contexto para IA estão atualizados, o servidor MCP
  de desenvolvimento responde pelo protocolo, scripts de primeira execução.
- `test_docs` - os dois idiomas têm as mesmas páginas e a mesma estrutura; links resolvem.

Checagens de drift: catálogo de ações (`docs/reference/actions.json`), OpenAPI
(`openapi-schema.yml`), docs de referência e arquivos para agentes gerados (`gen_docs.py --check`) -
regenere com os comandos do [guia de adicionar ação](add-an-action.md).
