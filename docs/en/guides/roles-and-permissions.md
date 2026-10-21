# Roles and permissions

Three layers decide whether a call succeeds. All three must say yes.

| Layer | Question | Where |
|---|---|---|
| Credential scope | Does this key, token or session hold the scope the action needs? | `@action(scope=...)`, `ApiKey.scopes`, OAuth consent |
| Role | Is the person's role in **this organization** allowed to do it? | `Membership.role`, read on **every** call |
| Tenant | Is the row in this organization? | `ctx.scoped`, `OrganizationScopedViewSet` |

## Roles

| Role | Writes tenant data | Creates API keys | Sees and revokes keys of others | Webhook endpoints |
|---|---|---|---|---|
| `owner` | yes | yes | yes (never obtains a working copy) | manage |
| `admin` | yes | yes | yes (never obtains a working copy) | manage |
| `member` | yes | yes (own keys) | no | read |
| `billing` | **no** | no | no | read |
| `auditor` | **no** | no | no | read |

`billing` and `auditor` are read-only: an action that writes returns `403 read_only_role` for them
whatever scopes the credential holds, and their keys can only ever carry read scopes.

The role is never copied into a token. Demoting or removing a person limits their keys and OAuth
tokens on the next call.

## Narrowing an action

```python
@action("invoices.void", write=True, roles={"owner", "admin"}, destructive=True, undoable=True)
def void_invoice(ctx, data): ...
```

`roles=` replaces the default write rule for that action. The catalog (`docs/reference/actions.json`)
records `roles`, so loosening it shows up in review.

## Scopes

A scope is `domain:level` (`notes:read`, `notes:write`). New ones appear with new actions. Profiles
for API keys: `read` (every read scope) and `full` (every scope the role allows). A key can be
narrower than its owner's role, never wider.

## Second factors

Staff must have an authenticator before `/admin/` opens (`STAFF_MFA_REQUIRED`). In production,
an owner or administrator signed in with a session must have one before the organization
endpoints answer (`ORG_PRIVILEGED_MFA_REQUIRED`): the API says why instead of a bare 403. Creating or rotating
an API key also needs a sign-in no older than `APIKEY_REQUIRE_RECENT_AUTH_SECONDS` (15 minutes),
and a password or second-factor reset revokes the person's keys.
