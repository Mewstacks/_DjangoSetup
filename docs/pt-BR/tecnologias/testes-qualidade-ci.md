# Testes, qualidade e CI

[English version](../../en/technologies/tests-quality-ci.md) ·
[Voltar à trilha](../trilha-aprendizado.md)

## Ferramentas

| Ferramenta | Função |
| --- | --- |
| pytest/pytest-django | Executar testes Python e Django |
| coverage | Mostrar caminhos exercitados |
| Ruff | Lint e formatação |
| mypy | Verificar tipos sem executar o código |
| pip-audit | Procurar vulnerabilidades conhecidas |
| pre-commit/Gitleaks | Detectar problemas e segredos antes do commit |
| GitHub Actions | Executar verificações automaticamente |
| uv/uv.lock | Instalar versões reproduzíveis |

## Tipos de teste

- **Unitário:** uma função ou regra isolada.
- **Integração:** Django com banco, cache ou API.
- **Contrato:** schema e formatos.
- **Segurança:** autorização, tenant, entrada maliciosa.
- **Operacional:** migration, build, deploy e restauração.

Para SaaS multi-tenant, teste um usuário em duas organizações e tente listar, ler, alterar e
excluir dados cruzados. Um caminho feliz não prova isolamento.

## Cobertura

Coverage mede linhas/caminhos executados, não qualidade. Um teste que não verifica o resultado
pode aumentar cobertura sem proteger nada.

Priorize:

- autenticação e permissions;
- isolamento de tenant;
- pagamentos e idempotência;
- criptografia/rotação;
- retenção e direitos LGPD;
- falhas de Redis/Celery;
- migrations.

## CI

A pipeline executa lint, formato, tipos, Django checks, migrations, OpenAPI, testes, auditoria de
dependências e build Docker. Se uma etapa falha, a mudança não deveria ser publicada.

Dependências são fixadas para reprodutibilidade. Atualize regularmente: lock antigo reproduz
também vulnerabilidades antigas.

## Limites

CI não substitui revisão humana, staging, teste de carga, restauração real, DAST/SAST ou pentest.
Ferramentas encontram classes de erro; regras de negócio inseguras exigem testes e análise
específicos.

Escreva o teste junto da regra. Para um bug de segurança, primeiro crie um teste que reproduz o
problema e depois confirme que a correção o faz passar.
