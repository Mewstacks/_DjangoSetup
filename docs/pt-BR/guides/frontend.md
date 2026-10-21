# Frontend e integração com SPA

O backend é uma API. Um cliente web ou mobile fala com ele de duas formas, e a escolha define como
se autentica.

| Cliente | Login | Carrega a sessão | Precisa de CSRF |
|---|---|---|---|
| `browser` (SPA num site seu) | `POST /api/v1/accounts/browser/v1/auth/login` | cookie de sessão | sim |
| `app` (mobile, desktop, SPA em outro site) | `POST /api/v1/accounts/app/v1/auth/login` | cabeçalho `X-Session-Token` | não |

Ambos são a API headless do django-allauth: cadastro (com `SIGNUP_ENABLED`), verificação de e-mail e
redefinição de senha por código, MFA (TOTP, WebAuthn, códigos de recuperação), sessões por
dispositivo. Todo fluxo pode responder "falta outra etapa" (verificar o endereço, informar o segundo
fator): leia `data.flows` na resposta em vez de supor que existe sessão. O login tem limite de
tentativas e bloqueio por conta e endereço do cliente; uma conta bloqueada responde `429` com
`Retry-After`.

## Chamando a API

```text
Authorization: Bearer <chave ou token OAuth>    # servidores, scripts, agentes
X-Session-Token: <token>                        # cliente app
Cookie: sessionid=...  +  X-CSRFToken: <token>  # cliente browser
X-Organization-ID: <uuid>                       # só sessões: qual tenant
Idempotency-Key: <1-128 caracteres>             # qualquer escrita que possa ser repetida
```

- `GET /api/v1/auth/csrf/` devolve o token CSRF do cliente browser. Envie-o em `X-CSRFToken` em toda
  requisição não segura.
- Uma credencial bearer fixa a própria organização; o cabeçalho é ignorado para ela.
- Não há "primeira organização" como padrão: uma sessão sem `X-Organization-ID` recebe
  `organization_required`. Liste as organizações com `GET /api/v1/organizations/`.
- Respostas de `/api/` têm `Cache-Control: no-store` e `Vary: X-Organization-ID`.

## CORS e cookies

Só `/api/` responde a requisições de outra origem (`CORS_URLS_REGEX`); páginas, o admin e as telas
OAuth nunca. Defina `DJANGO_CORS_ALLOWED_ORIGINS` (só https em produção) e
`DJANGO_CSRF_TRUSTED_ORIGINS` com a origem do seu frontend. Uma SPA em um *site diferente* do da API
precisa de `SESSION_COOKIE_SAMESITE=None` e `CSRF_COOKIE_SAMESITE=None` (a produção exige `Secure`
com elas) ou, mais simples, do cliente `app`. Cabeçalhos de requisição permitidos: `Authorization`,
`Content-Type`, `Idempotency-Key`, `X-CSRFToken`, `X-Organization-ID`, `X-Request-ID`,
`X-Session-Token`; expostos: `Retry-After`, `X-Request-ID`.

`Cross-Origin-Resource-Policy` é `same-origin` por padrão: imagens e arquivos servidos pela API não
podem ser incorporados por outra origem. Use `SECURE_CROSS_ORIGIN_RESOURCE_POLICY=same-site` quando
seu frontend for um subdomínio irmão que os incorpora.

## Content-Security-Policy

As páginas entregues (login, consentimento) só usam `'self'`: sem script ou estilo inline, sem
origens de terceiros. As violações são enviadas a `/api/v1/csp-report/` e registradas com a diretiva
e a *origem* do recurso bloqueado, nunca o caminho ou a query. Se seu produto serve HTML por este
serviço, mantenha-o compatível com a CSP ou amplie `SECURE_CSP` de propósito; não adicione
`'unsafe-inline'`.

## Gerando um cliente tipado

`openapi-schema.yml` (versionado e verificado no CI) descreve todo endpoint REST e, pelo catálogo de
ações, toda ação com seus JSON Schemas. Em desenvolvimento também é servido em `/api/schema/` e
exibido em `/api/docs/`.

```bash
npx openapi-typescript openapi-schema.yml -o src/api/schema.d.ts
```

Para ações, `GET /api/v1/actions/` lista as que o chamador pode usar com seus schemas de entrada e
saída, então um cliente pode ser gerado por credencial. Veja as
[convenções da API](api-conventions.md) para erros, paginação e idempotência.
