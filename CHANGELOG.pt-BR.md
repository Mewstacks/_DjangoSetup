# Changelog

English: [CHANGELOG.md](CHANGELOG.md)

## 2.1.0 - 2026-10-21 - revisão de segurança, LGPD e construção com IA

Incompatível (não havia produção; formatos mudaram no lugar): linhas de auditoria agora têm cadeia
com HMAC chaveado e exigem `AUDIT_HMAC_KEY`; o papel de runtime do banco não poda nem reescreve mais a
trilha de auditoria; ações de escrita devem declarar `undoable`; a produção exige `PUBLIC_URL`,
`PRIVACY_CONTROLLER_NAME`, contato do DPO e proxy declarado; `DEV_TOOLS_ALLOWED` substitui a flag
antiga de ferramentas de desenvolvimento. Veja [atualizando](docs/pt-BR/guides/upgrading.md).

### Adicionado
- Servidor MCP de desenvolvimento (`python -m devtools.mcp`), `manage.py scaffold`, `AGENTS.md`,
  `CLAUDE.md`, regras do Cursor e do Copilot, `llms.txt`, `llms-full.txt` e `conventions.json`
  gerados.
- Recursos MCP de runtime `platform://actions` e `platform://scopes`, e um prompt de uso.
- Suíte de conformidade parametrizada sobre toda ação registrada; lint do catálogo; teste da estrutura
  de tenancy.
- `scripts/bootstrap.py`, `init_project.py`, `remove_example.py`; `justfile`, `.editorconfig`,
  `.python-version`, CODEOWNERS, modelos de issue e PR, `LICENSE` MIT.
- LGPD: registro de consentimento de cookies, relatórios de impacto (RIPD), prazos e exportação de
  incidentes, retenção de contas inativas, eliminação de arquivos, ponto de encaixe de verificação de
  idade, consequência da recusa, e-mails em pt-BR.
- Docs: onze guias novos, cinco ADRs, quatro modelos de documento, checklist de quem constrói (en e
  pt-BR).
- CI: agenda semanal, matriz de Python, guarda de arquivos ignorados, Trivy, assinatura cosign,
  atestados, gate do GitHub Release.

### Alterado
- A guarda de rede aceita só endereços globalmente roteáveis (CGNAT, NAT64 e 6to4 eram brechas).
- Staff e papéis privilegiados de organização exigem MFA; chaves de API são revogadas na redefinição
  de senha; criar chave exige login recente.
- OAuth: tokens com hash, `iss` da RFC 9207, política de DCR; o verificador do MCP lê o IP real.
- Temporal: payload não selado recusado, TLS ou chave de API exigidos, ponte de tarefas restrita a
  prefixos declarados, flows carregam o próprio escopo.
- Links de exportação de privacidade são de uso único; URLs são removidas dos logs.
- Cabeçalhos CSP, Permissions-Policy e CORP; handlers de erro JSON; timeout de leitura do corpo.
- Deploy: papéis de banco separados para migração e runtime, limites de egress na NetworkPolicy, pods
  endurecidos.

### Corrigido
- `.gitignore` excluía `src/apps/uploads/`, então um clone limpo não iniciava.
- Os templates de produção liam variáveis de bucket que a documentação não citava.
