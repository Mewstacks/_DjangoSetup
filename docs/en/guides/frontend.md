# Frontend and SPA integration

The backend is an API. A browser or mobile client talks to it in one of two ways, and the choice
decides how it authenticates.

| Client | Sign in | Carries the session | Needs CSRF |
|---|---|---|---|
| `browser` (SPA on a site you control) | `POST /api/v1/accounts/browser/v1/auth/login` | session cookie | yes |
| `app` (mobile, desktop, a SPA on another site) | `POST /api/v1/accounts/app/v1/auth/login` | `X-Session-Token` header | no |

Both are the django-allauth headless API: sign-up (when `SIGNUP_ENABLED`), e-mail verification and
password reset by code, MFA (TOTP, WebAuthn, recovery codes), device sessions. Every flow can answer
"another step is needed" (verify the address, enter the second factor): read `data.flows` in the
response instead of assuming a session exists. Sign-in is rate limited and locked out per account
and client address; a locked account answers `429` with `Retry-After`.

## Calling the API

```text
Authorization: Bearer <key or OAuth token>      # servers, scripts, agents
X-Session-Token: <token>                        # app client
Cookie: sessionid=...  +  X-CSRFToken: <token>  # browser client
X-Organization-ID: <uuid>                       # sessions only: which tenant
Idempotency-Key: <1-128 chars>                  # any write you may retry
```

- `GET /api/v1/auth/csrf/` returns the CSRF token for the browser client. Send it back in
  `X-CSRFToken` on every unsafe request.
- A bearer credential fixes its own organization; the header is ignored for it.
- There is no "first organization" fallback: a session that omits `X-Organization-ID` gets
  `organization_required`. List organizations with `GET /api/v1/organizations/`.
- Responses to `/api/` are `Cache-Control: no-store` and `Vary: X-Organization-ID`.

## CORS and cookies

Only `/api/` answers cross-origin requests (`CORS_URLS_REGEX`); pages, the admin and the OAuth
screens never do. Set `DJANGO_CORS_ALLOWED_ORIGINS` (https only in production) and
`DJANGO_CSRF_TRUSTED_ORIGINS` to your front end's origin. A SPA on a *different site* than the API
needs `SESSION_COOKIE_SAMESITE=None` and `CSRF_COOKIE_SAMESITE=None` (production enforces `Secure`
with them) or, simpler, the `app` client. Allowed request headers: `Authorization`,
`Content-Type`, `Idempotency-Key`, `X-CSRFToken`, `X-Organization-ID`, `X-Request-ID`,
`X-Session-Token`; exposed: `Retry-After`, `X-Request-ID`.

`Cross-Origin-Resource-Policy` is `same-origin` by default: images and files served by the API
cannot be embedded by another origin. Use `SECURE_CROSS_ORIGIN_RESOURCE_POLICY=same-site` when your
front end is a sibling subdomain that embeds them.

## Content-Security-Policy

Shipped pages (sign-in, consent) are `'self'`-only: no inline script or style, no third-party
origins. Violations are posted to `/api/v1/csp-report/` and logged with the directive and the
*origin* of the blocked resource, never the path or query. If your product serves HTML from this
service, keep it CSP-clean or extend `SECURE_CSP` deliberately; do not add `'unsafe-inline'`.

## Generating a typed client

`openapi-schema.yml` (committed, checked in CI) describes every REST endpoint and, through the
action catalog, every action with its JSON Schemas. In development it is also served at
`/api/schema/` and rendered at `/api/docs/`.

```bash
npx openapi-typescript openapi-schema.yml -o src/api/schema.d.ts
```

For actions, `GET /api/v1/actions/` lists the ones the caller may use with their input and output
schemas, so a client can be generated per credential. See [API conventions](api-conventions.md)
for errors, pagination and idempotency.
