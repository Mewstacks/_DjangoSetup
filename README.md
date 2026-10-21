# Plataforma Django multi-tenant

[English](README.en.md) · [Documentação](docs/pt-BR/index.md)

Base para sistemas de qualquer tipo: Django 6.1, DRF, PostgreSQL, multi-tenant, com API e MCP
prontos, Temporal opcional, segurança estrita e ferramentas de LGPD.

**Uma função que você escreve vira** endpoint REST, ferramenta MCP, activity do Temporal e comando
de CLI, com escopo, papel, rate limit, idempotência, auditoria e undo.

```python
@action("notes.create", write=True)
def create_note(ctx: ActionContext, data: CreateNote) -> NoteOut:
    """Cria uma nota."""
    return NoteOut.of(services.create_note(ctx, title=data.title, body=data.body))
```

## O que vem pronto

| | |
|---|---|
| Ações e API | Registro de ações, REST em `/api/v1/actions/`, OpenAPI versionado |
| MCP | Servidor stateless em `/mcp`, OAuth 2.1 com PKCE e registro dinâmico, chaves de API |
| Contas | allauth: cadastro ligável, e-mail verificado, MFA (TOTP, WebAuthn), sessões |
| Fluxos | Temporal (cifrado, com contexto propagado) ou motor local; jobs agendados |
| LGPD | Catálogo de dados obrigatório, consentimento, requisições do titular, retenção, incidentes, RoPA |
| Segurança | Validadores estritos de produção, criptografia de campos com rotação, auditoria com cadeia de hash, SSRF-safe |
| Extras | Webhooks com outbox, feature flags, settings tipados, uploads validados |
| Operação | Logs JSON sem PII, OpenTelemetry, `doctor`, imagem única com papéis, compose, Kubernetes, Procfile |

## Começar

```bash
uv sync --all-extras
python scripts/bootstrap.py
python manage.py runserver
```

O `bootstrap` grava o `.env` com segredos novos, migra, semeia as finalidades da LGPD e cria
administrador verificado, organização e chave de API (exibida uma vez). Para outro nome:
`python scripts/init_project.py --name meu-produto`.

## Programar com IA (MCP)

São dois servidores MCP, com trabalhos diferentes:

| | Para quem | Faz o quê | Como sobe |
|---|---|---|---|
| `saas-devtools` | Quem **constrói** o produto (Claude Code, Cursor, Codex) | Ensina o projeto à IA: regras, framework, middleware, LGPD; gera recursos; roda o gate | `python -m devtools.mcp` (stdio, só local) |
| `/mcp` | Quem **usa** o produto em execução (agentes de clientes) | Cada ação vira uma ferramenta, com escopo, papel e auditoria | `MCP_ENABLED=true`, dentro do servidor |

### 1. Conectar o agente de desenvolvimento

O `.mcp.json` da raiz já registra o `saas-devtools`.

- **Claude Code:** abra o projeto na raiz e aprove o servidor quando perguntar (ou
  `claude mcp add saas-devtools -- uv run python -m devtools.mcp`). `/mcp` mostra o estado.
- **Cursor, Codex e outros:** registre o mesmo comando (`uv run python -m devtools.mcp`, com
  `DJANGO_SETTINGS_MODULE=config.settings.local`) no arquivo de MCP do cliente.

O `CLAUDE.md`, o `AGENTS.md` e `.cursor/rules` já mandam a IA seguir as regras do projeto.

### 2. Pedir a funcionalidade

> Adicione o recurso "faturas" com título, valor e vencimento. Use o MCP do projeto.

A IA segue este caminho (as ferramentas são do `saas-devtools`):

1. `describe_project` e `list_conventions`: entende apps, regras e definição de pronto.
2. `framework_guide` e `middleware_stack`: consulta como Django, DRF, Temporal e o middleware funcionam aqui, quando precisa.
3. `scaffold_resource` (primeiro `dry_run`): gera model, service, ações, undo, eventos, entrada de LGPD e testes.
4. `lgpd_check`: decide categorias, finalidade e eliminação de cada campo pessoal.
5. `check_conventions` e `run_gate`: corrige até ficar verde. Nada está pronto com o gate vermelho.

Você revisa o diff. Sem o MCP funciona igual: `python manage.py scaffold resource ...` e
`python scripts/verify.py --fast`.

### 3. Expor o produto a agentes de clientes

```bash
MCP_ENABLED=true OAUTH_ENABLED=true python manage.py runserver
python manage.py mcp_config --url http://localhost:8000 --org acme
```

`mcp_config` imprime os trechos prontos para Claude Code, Cursor e um teste com curl. A chave de API
do `bootstrap` autentica; os escopos da chave limitam as ferramentas. Detalhes no
[guia do MCP](docs/pt-BR/guides/mcp.md) e no [guia de IA](docs/pt-BR/guides/ai-development.md).

## Qualidade

`python scripts/verify.py` roda lint, tipos, testes, migrations e os checks de drift (catálogo de
ações, OpenAPI, docs geradas). O CI acrescenta PostgreSQL, pip-audit, bandit, gitleaks, zizmor,
hadolint, Trivy, CodeQL e SBOM.

## Aviso

Os controles técnicos ajudam em segurança e em evidência de responsabilização, mas não tornam um
produto automaticamente conforme à LGPD. Cada sistema ainda precisa de finalidades, bases legais,
retenção, fornecedores, avisos de privacidade e responsáveis próprios. Veja a
[matriz de conformidade](docs/pt-BR/lgpd/compliance-matrix.md).

Segurança: [SECURITY.md](SECURITY.md). Mudanças: [CHANGELOG.pt-BR.md](CHANGELOG.pt-BR.md). Licença: MIT.
