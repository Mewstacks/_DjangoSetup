# Contas, chaves de API e OAuth

## Pessoas: login

O django-allauth fornece JSON para apps e SPAs (`/api/v1/accounts/{app,browser}/v1/...`) e as
páginas HTML que o consentimento OAuth e o admin precisam (`/accounts/...`).

- O e-mail é a única identidade. O cadastro fica **fechado**, salvo `SIGNUP_ENABLED=true`.
- Endereço verificado é exigido antes da primeira sessão; verificação e redefinição de senha usam
  códigos de uso único. As respostas não revelam se um endereço existe.
- MFA: TOTP, chaves de segurança WebAuthn, códigos de recuperação. Sementes TOTP e códigos de
  recuperação são cifrados com o chaveiro de criptografia de campos.
- Sessões por dispositivo são listadas e revogáveis (`/accounts/sessions/`).
- O login do admin do Django passa pelo allauth, então MFA e verificação não são contornáveis.
- Cliente `app`: token em `X-Session-Token`; cliente `browser`: cookie de sessão com CSRF.

O antigo `POST /api/v1/auth/login/` continua por uma versão como descontinuado (a resposta traz
`Deprecation: true`); ele recusa contas com MFA ou endereço não verificado.

## Programas: chaves de API

Criadas por owners/admins por uma **sessão** (uma chave não cria chaves). Exibidas uma vez; só um
blind index é guardado. A chave tem escopos (lista explícita ou perfil `read` / `full`),
expiração opcional (máx. 365 dias), allowlist de IPs, `last_used_at` e revogação. A rotação é só
do owner e mantém a chave antiga válida por 24 horas.

`Authorization: Bearer <prefixo>_<id público>_<segredo>`. O papel do vínculo é checado a cada
chamada: rebaixar um usuário limita suas chaves na hora.

## Agentes e terceiros: OAuth

`OAUTH_ENABLED=true` monta authorize/token/revoke/introspect em `/o/` e os documentos de
descoberta. PKCE é obrigatório; a tela de consentimento mostra o cliente, o destino do redirect e
os escopos (os mesmos das chaves de API). Os tokens carregam audiência.

## Escolhendo

| Quem chama | Use |
|---|---|
| Pessoa no navegador | sessão via allauth |
| Mobile/SPA | cliente `app` do allauth |
| Script, servidor, CI | chave de API com os menores escopos |
| Cliente MCP / app de terceiros | OAuth com PKCE |
