# Servidor MCP

Toda ação cujos canais incluem `mcp` é uma tool. O servidor é HTTP streamable sem estado,
montado em `MCP_PATH` (padrão `/mcp`), opcionalmente por organização em `/mcp/<slug-da-org>`.

```bash
MCP_ENABLED=true  MCP_PUBLIC_URL=https://app.example.com
python manage.py mcp_config --url https://app.example.com --org acme
```

`mcp_config` imprime trechos prontos para Claude Code, JSON de Cursor/VS Code e um teste com
curl. Nunca imprime um segredo real.

## Autenticação

- **Chave de API**: `Authorization: Bearer <chave>`; os escopos limitam as tools listadas e
  chamáveis.
- **OAuth 2.1** (`OAUTH_ENABLED=true`): clientes usam authorization code com PKCE; o registro
  dinâmico de clientes é limitado e desligado para anônimos, salvo `OAUTH_DCR_ANONYMOUS=true`.
  Tokens são vinculados à audiência da URL do MCP (RFC 8707). Metadados:
  `/.well-known/oauth-authorization-server` e `/.well-known/oauth-protected-resource`.

## O que os agentes recebem

- Tools geradas dos schemas pydantic, com `readOnlyHint`/`destructiveHint` derivados da ação, de
  modo que nunca divergem de `write`.
- Toda chamada é auditada com canal `mcp`; escritas guardam snapshot de undo
  (`ACTIONS_JOURNAL_CHANNELS`, mantido por `ACTIONS_JOURNAL_RETENTION_DAYS`).
- `agent.report` registra o tempo gasto pelo agente num ledger (`AgentRun`).

## Notas operacionais

- O app MCP não passa pelos middlewares do Django; por isso tem pré-voo próprio: IP confiável do
  cliente, request id, orçamento por IP (`MCP_RATE_PER_MINUTE_IP`), teto de corpo, guarda de
  Host/Origin (`MCP_ALLOWED_ORIGINS`).
- Sem CORS por padrão; navegadores não são clientes MCP.
- Um teste de paridade garante que a mesma ação por REST e por MCP gera os mesmos campos de
  auditoria.
