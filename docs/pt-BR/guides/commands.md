# Comandos de gerenciamento

Rode com `python manage.py <comando>` (ou `entrypoint manage <comando>` na imagem). Comandos só
locais recusam rodar a menos que `DEV_TOOLS_ALLOWED` esteja ligado, o que só as configurações local e
de teste fazem.

| Comando | O que faz |
|---|---|
| `bootstrap` *(local)* | Um superusuário verificado, uma organização e uma chave de API, de forma idempotente; imprime as credenciais uma vez |
| `scaffold resource <app> <Model> --fields ...` *(local)* | Gera um recurso de tenant que segue as regras; `--dry-run` lista os arquivos |
| `action list` / `action run <nome> --as <email> --org <slug> --json '{}'` | O catálogo de ações pelo shell; executa uma ação como uma pessoa |
| `actions_catalog [--check]` | Escreve ou verifica `docs/reference/actions.json` |
| `mcp_config --url ... --org ...` | Imprime a configuração de cliente MCP pronta para colar (nunca um segredo) |
| `doctor [--strict]` | A implantação está sã: banco, cache, criptografia, HTTPS, e-mail, flows, MCP, cadeia de auditoria e seus privilégios, configuração de privacidade |
| `audit_verify [--org ID] [--json] [--expect heads.json]` | Recalcula as cadeias de hash da auditoria; registra cada cabeça e depois prova que os eventos mais novos não foram removidos |
| `reencrypt_fields [--dry-run]` | Recifra toda coluna cifrada e os segredos de MFA com a chave ativa |
| `privacy_seed [--notice-url URL]` | Finalidades de base e rascunhos inativos de suboperadores |
| `privacy_ropa` | Exporta o registro das operações de tratamento a partir do catálogo |
| `privacy_incident_export REF [--format md]` | Monta o conteúdo da comunicação de incidente à ANPD |
| `retention_sweep [--dry-run]` | Apaga ou anonimiza dados além da retenção da finalidade |
| `flag ...` | Lê e define feature flags e configurações |
| `flows_sync`, `flows_worker`, `run_scheduler` | Schedules do Temporal, o worker do Temporal, o agendador estilo cron |
| `run_job NOME` / `run_job --due` | Executa um job, ou o que estiver vencido agora |
| `spectacular --file ...` | Gera o OpenAPI (veja `scripts/check_openapi.py`) |

## Scripts

| Script | Finalidade |
|---|---|
| `scripts/bootstrap.py` | `.env`, migração, seed, administrador, organização, chave: primeira execução num comando |
| `scripts/init_project.py --name ...` | Renomeia o template para o seu produto |
| `scripts/remove_example.py` | Remove o recurso de exemplo |
| `scripts/verify.py [--fast]` | O gate de qualidade que o CI roda |
| `scripts/gen_docs.py [--check]` | Docs de referência e os arquivos de contexto para IA |
| `scripts/check_openapi.py [--write]` | O arquivo OpenAPI versionado |
| `scripts/generate_production_secrets.py` | Segredos de produção, na saída padrão |
| `scripts/e2e_smoke.py` | Teste de fumaça pós-deploy contra uma instância em execução |

O servidor MCP de desenvolvimento (`python -m devtools.mcp`) expõe a maior parte disso a um agente
de IA; veja [Construindo com um agente de IA](ai-development.md).
