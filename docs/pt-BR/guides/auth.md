# Contas, chaves de API e OAuth

## Pessoas: login

O django-allauth fornece JSON para apps e SPAs (`/api/v1/accounts/{app,browser}/v1/...`) e as
páginas HTML que o consentimento OAuth e o admin precisam (`/accounts/...`).

- O e-mail é a única identidade. O cadastro fica **fechado**, salvo `SIGNUP_ENABLED=true`.
- Endereço verificado é exigido antes da primeira sessão; verificação e redefinição de senha usam
  códigos de uso único. As respostas não revelam se um endereço existe.
- MFA: TOTP, chaves de segurança WebAuthn, códigos de recuperação. Sementes TOTP e códigos de
  recuperação são cifrados com o chaveiro de criptografia de campos; uma semente guardada sem
  cifra é recusada.
- **Staff precisa de um segundo fator** antes de `/admin/` abrir (`STAFF_MFA_REQUIRED`, ligado). Em
  produção, owners e admins precisam de um antes que a sessão deles use os endpoints da organização
  (`ORG_PRIVILEGED_MFA_REQUIRED`).
- Mudar o endereço, a senha ou o segundo fator pede a senha de novo
  (`ACCOUNT_REAUTHENTICATION_REQUIRED`, 5 minutos).
- Sessões por dispositivo são listadas e revogáveis (`/accounts/sessions/`).
- O login do admin do Django passa pelo allauth, então MFA e verificação não são contornáveis.
  Staff sem `is_superuser` não vê, não edita nem redefine superusuários, não muda o e-mail de ninguém
  e não define senhas pelo admin.
- Cliente `app`: token em `X-Session-Token`; cliente `browser`: cookie de sessão com CSRF. Veja o
  [guia de frontend](frontend.md).
- O login tem bloqueio por conta e endereço do cliente (django-axes) em **todos** os caminhos: os
  endpoints do allauth e, se ligado, o legado.

O login JSON só com senha `POST /api/v1/auth/login/` vem **desligado** (`LEGACY_LOGIN_ENABLED=false`
responde 404). Ligue só para migrar um cliente antigo; ele ainda recusa contas com MFA ou endereço não
verificado, e suas respostas trazem `Deprecation: true`.

## Programas: chaves de API

Criadas por owners, admins e members por uma **sessão** (uma chave não cria chaves). Exibidas uma vez;
só um blind index com chave é guardado. Criar ou rotacionar uma exige um login com no máximo
`APIKEY_REQUIRE_RECENT_AUTH_SECONDS` (900), para que uma sessão parada roubada não crie uma credencial
que a sobreviva. A chave tem escopos (lista explícita ou perfil `read` / `full`), expiração opcional
(máx. 365 dias), allowlist de IPs (CIDRs validados, no máximo 20), `last_used_at` e revogação. A
rotação é só do owner e mantém a chave antiga válida por 24 horas. Teto por organização:
`QUOTA_API_KEYS_PER_ORG`.

Uma redefinição de senha ou mudança do segundo fator **revoga as chaves da pessoa**
(`APIKEY_REVOKE_ON_CREDENTIAL_RESET`): elas autenticam como o dono sem segundo fator, então deixá-las
vivas depois de uma suspeita de invasão deixaria o invasor dentro.

`Authorization: Bearer <prefixo>_<id público>_<segredo>`. O papel do vínculo é checado a cada
chamada: rebaixar um usuário limita suas chaves na hora. Tentativas falhas são contadas por id de
chave **e** endereço, e por endereço no total, então um estranho não bloqueia o dono, e espalhar muitos
ids a partir de um lugar é contido.

Rotacionar `PRIVACY_HMAC_KEY` sem invalidar chaves: liste o valor antigo em
`PRIVACY_HMAC_KEYS_PREVIOUS`; uma chave encontrada sob a chave antiga é regravada sob a nova no primeiro
uso ([hardening](../security/hardening.md)).

## Agentes e terceiros: OAuth

`OAUTH_ENABLED=true` monta authorize/token/revoke/introspect em `/o/` mais os documentos de
descoberta. PKCE (`S256`) é obrigatório; o consentimento lista o cliente, seu id, quando se
registrou, o destino do redirecionamento e os escopos (os mesmos das chaves de API). Os tokens carregam
uma audiência (RFC 8707) e são guardados só como checksum SHA-256; refresh tokens rotacionam e uma
repetição revoga a família inteira; as respostas de autorização trazem o parâmetro `iss` da RFC 9207.
Detalhes no [guia do MCP](mcp.md).

## Escolhendo

| Quem chama | Use |
|---|---|
| Pessoa no navegador | sessão via allauth |
| Mobile/SPA | cliente `app` do allauth |
| Script, servidor, CI | chave de API com os menores escopos |
| Cliente MCP / app de terceiros | OAuth com PKCE |
