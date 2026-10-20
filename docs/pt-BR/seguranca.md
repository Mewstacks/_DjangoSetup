# Modelo de segurança

[English version](../en/security.md)

## Controles padrão

- Redirecionamento HTTPS, cookies Secure/HTTP-only/SameSite, HSTS, hosts/origens restritos, CSRF,
  escaping XSS, proteção contra clickjacking, MIME sniffing, referrer policy e CSP.
- Senhas Argon2 com mínimo de 12 caracteres, bloqueio de tentativas, erros genéricos e throttling
  compartilhado no Redis.
- django-axes normaliza a conta atacada e recebe o request original. Throttles por IP ignoram
  `X-Forwarded-For` informado pelo cliente e usam somente o IP validado pelo backend.
- APIs JSON autenticadas por padrão, paginação e uploads limitados, CORS explícito e request IDs.
- Container não-root, dependências fixadas, lint, testes, auditoria de dependências, busca de
  segredos e build da imagem no CI.
- Logs e Sentry sem dados pessoais: bodies, queries, cookies, usuário e credenciais são removidos.

## Rate limiting e bloqueio

Os buckets de throttling usam `apps.common.network.client_ip`, que confia apenas no peer direto
(`REMOTE_ADDR`), a menos que proxies confiáveis sejam configurados — `TRUSTED_PROXY_IPS` (CIDRs
dos proxies) ou `TRUSTED_PROXY_COUNT` (número de proxies na frente). O `get_ident` do DRF lê o
`X-Forwarded-For` enviado pelo cliente quando `NUM_PROXIES` não está definido, o que permite criar
um bucket novo a cada requisição; por isso `NUM_PROXIES` é fixado em `0` e todos os throttles
derivam de `apps.common.throttling`. É agnóstico de host; ajuste as duas variáveis conforme sua
borda (atrás de um proxy reverso, `TRUSTED_PROXY_COUNT=1`).

O bloqueio é por `(username, ip_address)`. Use `AXES_LOCKOUT_BY_USERNAME=true` para bloquear
também apenas por usuário, o que barra força bruta distribuída em muitos IPs, mas permite que um
terceiro bloqueie uma conta de propósito.

`SESSION_COOKIE_SAMESITE` e `CSRF_COOKIE_SAMESITE` usam `Lax`, que pressupõe cliente same-site.
Uma SPA servida de outro site exige `None`, e a produção só aceita esse valor com cookies HTTPS.

## Criptografia

Criptografia de infraestrutura e da aplicação protegem ameaças diferentes:

- Fly Managed Postgres protege transporte e mídia de armazenamento.
- HTTPS protege o transporte da API.
- `EncryptedTextField` usa AES-256-GCM, nonce novo de 96 bits e autenticação do ciphertext.
- O nome do model e da coluna é usado como AAD, impedindo que um ciphertext seja movido
  silenciosamente para outra coluna.
- Cada ciphertext é vinculado ao seu modelo e coluna via associated data do GCM, então não é
  possível mover um valor para outro campo e ainda decriptá-lo. A identidade da linha não entra
  no vínculo porque a chave primária não está disponível quando o Django lê o campo do banco:
  a troca entre linhas da mesma coluna, por quem tenha escrita no banco, continua possível.
- Chaves de campo e HMAC são independentes da chave de assinatura do Django. A produção não
  inicia sem elas.

Mantenha a chave ativa e chaves antigas somente para decriptação em `FIELD_ENCRYPTION_KEYS`.
Para rotacionar: adicione uma chave, torne-a ativa, publique, regrave registros em lotes,
confirme que a chave antiga não é mais usada e remova-a apenas após expirar os backups.

O AAD por coluna altera o formato autenticado: ciphertexts gravados pela implementação anterior
precisam ser lidos no formato legado e regravados por uma migração testada. O vínculo não inclui
o ID da linha, portanto não impede troca entre registros da mesma coluna.

Não criptografe tudo apenas por aparência. Ciphertext aleatório não é pesquisável e pode
quebrar unicidade. Use criptografia de aplicação para texto confidencial, tokens,
identificadores e narrativas de incidentes/solicitações.

## Limitações de autenticação

A sessão é o padrão para aplicações próprias same-site. O starter não inclui cadastro público,
recuperação de senha, MFA, SSO empresarial ou API keys. Antes de expor acesso privilegiado,
adicione WebAuthn/TOTP ou OIDC com MFA. Mantenha o Django Admin desabilitado ou restrito.

`AXES_LOCKOUT_BY_USERNAME=true` reduz ataques distribuídos contra uma conta, mas também permite
lockout proposital por terceiros. Avalie esse trade-off antes de habilitar.

## Trabalho obrigatório antes da produção

- Use edge/WAF com rate limiting contra ataques volumétricos e bots.
- Restrinja a organização Fly, exija MFA/SSO e separe produção de não produção.
- Configure scrubbers e retenção mínima no Sentry.
- Atualize dependências e acompanhe avisos de Django, Fly, PostgreSQL, Redis e Sentry.
- Faça threat modeling, SAST/DAST, testes de restauração e pentest independente para alto risco.

Consulte o [runbook de incidentes](runbooks/resposta-incidentes.md) e o
[runbook de backup/restauração](runbooks/backup-restauracao.md).
