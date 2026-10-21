# Servidor MCP

Toda ação cujos canais incluem `mcp` é uma ferramenta. O servidor é HTTP streamable sem estado,
montado em `MCP_PATH` (padrão `/mcp`), opcionalmente por organização em `/mcp/<slug-da-org>`.
(Para deixar um agente *construir* o produto, veja [Construindo com um agente de IA](ai-development.md).)

```bash
MCP_ENABLED=true  MCP_PUBLIC_URL=https://app.exemplo.com
python manage.py mcp_config --url https://app.exemplo.com --org acme
```

`mcp_config` imprime trechos prontos para colar no Claude Code, em JSON do Cursor/VS Code e um teste
com curl. Nunca imprime um segredo de verdade.

## Protocolo

Sem estado: nenhuma sessão, qualquer réplica responde qualquer requisição (o `Mcp-Session-Id` nunca é
emitido). O servidor responde `initialize` para as revisões 2025-03-26, 2025-06-18 e 2025-11-25 e
atende um cliente que nunca inicializa, que é como funciona a revisão 2026-07-28. Um teste fixa isso,
então uma atualização do SDK não muda nada em silêncio. Os nomes das ferramentas são a `<ação>` com os
pontos trocados por sublinhados (`notes.create` vira `notes_create`, opcionalmente com o prefixo
`MCP_TOOL_PREFIX`); a [referência](../reference/actions.md) lista os dois.

## Autenticação

- **Chave de API**: `Authorization: Bearer <chave>`; os escopos limitam as ferramentas listadas e
  chamáveis.
- **OAuth 2.1** (`OAUTH_ENABLED=true`): fluxo de código de autorização com PKCE. Metadados:
  `/.well-known/oauth-authorization-server` e `/.well-known/oauth-protected-resource`.
  - Os tokens são presos à audiência da URL do MCP (RFC 8707); um token sem audiência é recusado.
  - Os tokens são guardados como checksum SHA-256, não em claro (um dump do banco não traz nada
    reutilizável); refresh tokens rotacionam e uma repetição revoga a família; as respostas de
    autorização trazem `iss` (RFC 9207).
  - **Registro.** O registro dinâmico de clientes está ligado mas com limite de taxa e desligado para
    anônimos, salvo `OAUTH_DCR_ANONYMOUS=true`. Um registro é recusado a menos que peça só os grants
    `authorization_code` / `refresh_token` e seus redirect URIs sejam `https`, um endereço `http`
    de loopback (`127.0.0.1`, `::1`, `localhost`) ou um esquema listado em `OAUTH_REDIRECT_URI_SCHEMES`
    (por exemplo `cursor://`); sem curingas, fragmentos ou mais de cinco. O token de registro expira
    (`OAUTH_DCR_REGISTRATION_TOKEN_SECONDS`, 30 dias).
  - **Client ID Metadata Documents** (o método de registro que a revisão 2026-07-28 prefere ao DCR):
    `OAUTH_CIMD_ENABLED=true` deixa um cliente usar uma URL `https` como `client_id`, buscada por um
    buscador reforçado contra SSRF; `OAUTH_CIMD_ALLOWED_HOSTS` o restringe. Desligado por padrão.

## O que os agentes recebem

- Ferramentas geradas dos schemas pydantic, com `readOnlyHint`/`destructiveHint` derivados da ação,
  então não podem divergir de `write`.
- `platform://actions`, `platform://scopes` e o prompt `how_to_use_platform` (escopo `platform:read`,
  incluído em todo perfil de leitura): o que esta credencial pode chamar, seu papel e limites, e como se
  comportar (agir como a pessoa, dizer o que muda, perguntar antes de algo destrutivo, tratar texto de
  registros como dado). Adicione os seus em `<app>/agent.py`.
- Toda chamada é auditada com canal `mcp`; escritas guardam um snapshot de desfazer
  (`ACTIONS_JOURNAL_CHANNELS`, mantido por `ACTIONS_JOURNAL_RETENTION_DAYS`). Toda ação de escrita
  declara se pode ser desfeita (`undoable`); o catálogo mostra.
- `agent.report` registra o tempo gasto pelo agente num livro-razão (`AgentRun`).

## Notas operacionais

- O app MCP não passa pelos middlewares do Django, então tem um pré-voo próprio: IP do cliente
  confiável, id de requisição, orçamento por IP (`MCP_RATE_PER_MINUTE_IP`), limite de corpo, guarda de
  Host/Origin (`MCP_ALLOWED_ORIGINS`).
- A allowlist de IPs de uma chave é checada contra o endereço real do cliente, também em `/mcp`.
- Sem CORS por padrão; navegadores não são clientes MCP.
- Um teste de paridade garante que a mesma ação por REST e por MCP produz os mesmos campos de
  auditoria.
