# Accounts, API keys and OAuth

## People: sign-in

django-allauth provides both JSON for apps and SPAs (`/api/v1/accounts/{app,browser}/v1/...`) and
the HTML pages OAuth consent and the admin need (`/accounts/...`).

- Email is the only identity. Sign-up is **closed** unless `SIGNUP_ENABLED=true`.
- A verified address is required before the first session; verification and password reset use
  one-time codes. Responses do not reveal whether an address exists.
- MFA: TOTP, WebAuthn security keys, recovery codes. TOTP seeds and recovery codes are encrypted
  with the field-encryption key ring.
- Device sessions are listed and revocable (`/accounts/sessions/`).
- The Django admin login is routed through allauth, so MFA and verification cannot be bypassed.
- `app` client: token in `X-Session-Token`; `browser` client: session cookie with CSRF.

The old `POST /api/v1/auth/login/` remains for one release as deprecated (response carries
`Deprecation: true`); it refuses accounts that have MFA or an unverified address.

## Programs: API keys

Created by owners/admins through a **session** (a key cannot mint keys). Shown once; only a blind
index is stored. A key has scopes (explicit list, or profile `read` / `full`), optional expiry
(max 365 days), an IP allow-list, `last_used_at` and revocation. Rotation is owner-only and keeps
the old key valid for 24 hours.

`Authorization: Bearer <prefix>_<public id>_<secret>`. The membership role is checked on every
call: demoting a user immediately limits their keys.

## Agents and third parties: OAuth

`OAUTH_ENABLED=true` mounts authorize/token/revoke/introspect under `/o/` plus discovery
documents. PKCE is mandatory; consent lists the client, its redirect destination and the scopes
(the same scopes as API keys). Tokens carry an audience.

## Choosing

| Caller | Use |
|---|---|
| Person in a browser | session via allauth |
| Mobile/SPA | allauth `app` client |
| Script, server, CI | API key with the narrowest scopes |
| MCP client / third-party app | OAuth with PKCE |
