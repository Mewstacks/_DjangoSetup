# Accounts, API keys and OAuth

## People: sign-in

django-allauth provides both JSON for apps and SPAs (`/api/v1/accounts/{app,browser}/v1/...`) and
the HTML pages OAuth consent and the admin need (`/accounts/...`).

- Email is the only identity. Sign-up is **closed** unless `SIGNUP_ENABLED=true`.
- A verified address is required before the first session; verification and password reset use
  one-time codes. Responses do not reveal whether an address exists.
- MFA: TOTP, WebAuthn security keys, recovery codes. TOTP seeds and recovery codes are encrypted
  with the field-encryption key ring; a stored seed that is not encrypted is refused.
- **Staff need a second factor** before `/admin/` opens (`STAFF_MFA_REQUIRED`, on). In production
  owners and administrators need one before their session can use the organization endpoints
  (`ORG_PRIVILEGED_MFA_REQUIRED`).
- Changing the address, the password or the second factor asks for the password again
  (`ACCOUNT_REAUTHENTICATION_REQUIRED`, 5 minutes).
- Device sessions are listed and revocable (`/accounts/sessions/`).
- The Django admin login is routed through allauth, so MFA and verification cannot be bypassed.
  Staff without `is_superuser` cannot see, edit or reset superusers, cannot change anyone's e-mail
  and cannot set passwords from the admin.
- `app` client: token in `X-Session-Token`; `browser` client: session cookie with CSRF. See the
  [frontend guide](frontend.md).
- Sign-in is locked out per account and client address (django-axes), on **every** path: the allauth
  endpoints and, if enabled, the legacy one.

The password-only JSON login `POST /api/v1/auth/login/` is **off** (`LEGACY_LOGIN_ENABLED=false`
answers 404). Enable it only to migrate an old client; it still refuses accounts that have MFA or
an unverified address, and its responses carry `Deprecation: true`.

## Programs: API keys

Created by owners, administrators and members through a **session** (a key cannot mint keys). Shown
once; only a keyed blind index is stored. Creating or rotating one needs a sign-in no older than
`APIKEY_REQUIRE_RECENT_AUTH_SECONDS` (900), so a stolen idle session cannot mint a credential that
outlives it. A key has scopes (explicit list, or profile `read` / `full`), optional expiry (max 365
days), an IP allow-list (validated CIDRs, at most 20), `last_used_at` and revocation. Rotation is
owner-only and keeps the old key valid for 24 hours. Per-organization ceiling: `QUOTA_API_KEYS_PER_ORG`.

A password reset or a change to the second factor **revokes the person's keys**
(`APIKEY_REVOKE_ON_CREDENTIAL_RESET`): they authenticate as their owner with no second factor, so
leaving them alive after a suspected takeover would leave the attacker in.

`Authorization: Bearer <prefix>_<public id>_<secret>`. The membership role is checked on every
call: demoting a user immediately limits their keys. Failed attempts are counted per key id **and**
address and per address overall, so a stranger cannot lock the owner out, and spraying many ids from
one place is stopped.

Rotating `PRIVACY_HMAC_KEY` without invalidating keys: list the old value in
`PRIVACY_HMAC_KEYS_PREVIOUS`; a key found under an old key is rewritten under the new one on first
use ([hardening](../security/hardening.md)).

## Agents and third parties: OAuth

`OAUTH_ENABLED=true` mounts authorize/token/revoke/introspect under `/o/` plus discovery
documents. PKCE (`S256`) is mandatory; consent lists the client, its id, when it registered, its
redirect destination and the scopes (the same scopes as API keys). Tokens carry an audience
(RFC 8707) and are stored only as a SHA-256 checksum; refresh tokens rotate and a replay revokes the
whole family; authorization responses carry the RFC 9207 `iss` parameter. Details in the
[MCP guide](mcp.md).

## Choosing

| Caller | Use |
|---|---|
| Person in a browser | session via allauth |
| Mobile/SPA | allauth `app` client |
| Script, server, CI | API key with the narrowest scopes |
| MCP client / third-party app | OAuth with PKCE |
