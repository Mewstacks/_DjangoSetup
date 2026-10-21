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

## Construir com IA

`AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, `.github/copilot-instructions.md` e `llms.txt` são gerados
de um só livro de regras e checados no CI. O servidor MCP de desenvolvimento
(`python -m devtools.mcp`, já em `.mcp.json`) deixa Claude, GPT ou qualquer agente descrever o
projeto, gerar um recurso (`manage.py scaffold`), checar convenções e LGPD, e rodar o gate. Veja o
[guia de IA](docs/pt-BR/guides/ai-development.md).

Depois: [início rápido](docs/pt-BR/quickstart.md), [arquitetura](docs/pt-BR/architecture.md),
[adicionar uma ação](docs/pt-BR/guides/add-an-action.md).

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
