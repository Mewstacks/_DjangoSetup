# Modelo de ameaças

| Ativo | Ameaça | Controle |
|---|---|---|
| Dados de outra organização | IDOR, filtro de tenant esquecido, FK gravável para linha alheia | Porta única do ORM nas ações (`ctx.scoped`, teste AST), `OrganizationScopedViewSet`, `OrgScopedPrimaryKeyRelatedField`, papel checado a cada chamada |
| Credenciais | Força bruta, credential stuffing, enumeração | Argon2, lockout do axes (buckets IPv6 /64), rate limits do allauth, respostas uniformes, MFA |
| Chaves de API | Roubo, excesso de privilégio, chave criando chave | Blind index, escopos com negação por padrão, allowlist de IP, expiração, criação só por sessão, 24 h de sobreposição na rotação |
| Tokens (OAuth) | Replay em outro serviço | PKCE, vínculo de audiência (RFC 8707), vida curta |
| Segredos no banco | Vazamento de dump ou backup | Criptografia AES-GCM de campos com chaveiro e rotação (`reencrypt_fields`), sementes MFA cifradas, respostas de idempotência e snapshots de undo cifrados |
| Logs e traces | Vazamento de PII | Redação no fim do pipeline, teste de log dourado, payloads do Temporal cifrados |
| Chamadas de saída | SSRF, DNS rebinding | `netguard`: https, endereços públicos, IP fixado, sem redirects |
| Uploads | Malware, polyglots, zip bombs, XSS armazenado | Sniffing de conteúdo, regras de extensão/dupla extensão, limites de zip, attachment + nosniff + CSP sandbox, ClamAV opcional |
| Trilha de auditoria | Adulteração | Cadeia de hash por organização, trigger no banco bloqueia UPDATE/DELETE, âncoras na poda, `audit_verify` |
| Disponibilidade | Corpos grandes, inundação | Teto de corpo ASGI, orçamentos por IP e por credencial, respostas limitadas |
| Cadeia de suprimento | Dependência vulnerável ou maliciosa | Deps travadas, pip-audit, Dependabot, SBOM, Actions e imagens fixadas, Trivy, proveniência |
| Agentes (MCP) | Ações destrutivas induzidas por prompt | Escopos, papel, dicas `destructive`, journal de undo, ledger de runs, texto em registros tratado como dado |

Fora de escopo: host ou pipeline de build comprometidos, superusuários maliciosos (mitigados por
auditoria e allowlist do admin, não impedidos), SSO/SCIM.
