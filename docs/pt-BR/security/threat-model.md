# Modelo de ameaças

| Ativo | Ameaça | Controle |
|---|---|---|
| Dados de outra organização | IDOR, filtro de tenant ausente, FK gravável para linha alheia | Porta única do ORM nas ações (`ctx.scoped`, teste de AST sobre `actions.py`, `actions/*.py`, `agent.py`), `OrganizationScopedViewSet`, `OrgScopedPrimaryKeyRelatedField`, toda coluna de organização escopada ou explicada (teste), desfazer filtra por organização, papel checado a cada chamada; row-level security é uma opção documentada ([ADR 14](../adr/row-level-security.md)) |
| Capacidade compartilhada | Um tenant enche o banco, o bucket ou a tabela de chaves | Cotas por organização (`QUOTA_*`) |
| Credenciais | Força bruta, credential stuffing, enumeração | Argon2, bloqueio axes em todo caminho de login (buckets /64 de IPv6), limites do allauth, respostas uniformes, MFA |
| Contas privilegiadas | Tomada de superusuário por staff; admin só com senha | Superusuários ocultos de outro staff, e-mail e troca de senha só do superusuário, MFA exigido para o admin e (produção) para owners e admins |
| Chaves de API | Roubo, excesso de privilégio, chave que cria chave, sobrevivência a uma invasão | Armazenamento com blind index chaveado, escopos default-deny, allowlist de IPs validada, expiração, criação só por sessão com login recente, sobreposição de rotação de 24 h, revogadas na redefinição de senha / MFA, falhas contadas por chave+endereço |
| Tokens (OAuth) | Replay em outro serviço; dump do banco | PKCE `S256`, audiência (RFC 8707), guardados como checksum, refresh rotativo com revogação da família, `iss` da RFC 9207, só redirecionamentos https/loopback, registro limitado e verificado por política |
| Segredos no banco | Dump ou vazamento de backup | Criptografia AES-GCM de campos com chaveiro e rotação (`reencrypt_fields`, sementes de MFA inclusas), respostas de idempotência e snapshots de desfazer cifrados, tokens como checksum |
| Logs e traces | Vazamento de PII | Redação no fim do pipeline (inclusive objetos renderizados com `str`), caminhos de URL secretos removidos, teste de log dourado, cifra de payload do Temporal |
| Chamadas de saída | SSRF, DNS rebinding, endereços privados em túnel | `netguard`: https, só endereços globais, IP fixado, sem redirecionamentos, sem proxy do ambiente, prazo, sem descompressão; a saída da NetworkPolicy exclui faixas privadas |
| Exportação do titular | Um link por e-mail que sobrevive à sua finalidade | Arquivo selado, link que expira limitado a `PRIVACY_EXPORT_MAX_DOWNLOADS`, token removido dos logs, `PUBLIC_URL` absoluta |
| Uploads | Malware, polyglots, zip bombs, XSS armazenado, arquivos órfãos | Detecção de conteúdo, regras de extensão, limites de zip, anexo + nosniff + sandbox CSP, ClamAV opcional, arquivo removido com a linha em todo caminho |
| Trilha de auditoria | Adulteração por conta comprometida da aplicação ou por quem escreve no banco | Cadeia de hash chaveada por organização, função de poda só do dono, papel de runtime só com `INSERT`/`SELECT`, `CHECK` contra linhas fora da cadeia, `audit_verify` e exportação de cabeças ([ADR 13](../adr/audit-chain-and-role-split.md)) |
| Motor de workflows | Um estranho na rede do Temporal inicia uma atividade como qualquer pessoa | Payloads selados exigidos (um não selado é recusado), TLS ou chave de API validados na partida, `run_task` limitado a tarefas declaradas sob prefixos permitidos |
| Disponibilidade | Corpos grandes ou lentos, enxurradas | Limite e timeout de corpo no ASGI, orçamentos por IP e por credencial, respostas limitadas |
| Cadeia de suprimentos | Dependência vulnerável ou maliciosa, imagem adulterada | Deps travadas, `pip-audit` semanal do `uv.lock`, Dependabot, SBOM, Actions e imagens fixadas, Trivy, CodeQL, zizmor, release condicionado ao CI, assinatura cosign, proveniência, deploy por digest |
| Agentes (MCP) | Ações destrutivas induzidas por prompt | Escopos, papel, dicas `destructive`, decisão explícita de desfazer por ação de escrita, diário de desfazer, livro de execuções, texto de registros tratado como dado, prompt de comportamento |
| O próprio código | Uma mudança (humana ou de IA) que remove um controle | Regras impostas por testes, suíte de conformidade sobre toda ação, arquivos para agentes gerados e mantidos atualizados, `check_conventions` |

Fora de escopo: host ou pipeline de build comprometido, superusuários maliciosos que também tenham as
chaves (mitigados por auditoria e pela allowlist do admin, não impedidos), SSO/SCIM, negação de serviço
na camada de rede.
