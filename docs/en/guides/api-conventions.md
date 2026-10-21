# API conventions

One set of rules for every endpoint, so a client written for one works for the next.

## Errors

Every error, from every surface (REST, MCP, middleware, lockout), has one envelope:

```json
{"error": {"status": 422, "code": "invalid", "detail": "Invalid input.", "request_id": "..."}}
```

`detail` is text written for the caller; for validation it is a list of `{field, message}` and
**never echoes the input** (it may be personal data). `code` is stable and meant for programs.
Internal errors are `500 server_error` with nothing but the `request_id` (also the
`X-Request-ID` response header): quote it to the operator.

| Status | Codes you will meet |
|---|---|
| 400 | DRF field validation on classic viewsets |
| 401 | `authentication_required`; a bad key or token is one generic 401 with `WWW-Authenticate` |
| 403 | `forbidden`, `missing_scope`, `read_only_role`, `role_forbidden`, `quota_exceeded`, `reauthentication_required`, `mfa_required` |
| 404 | `not_found` (also for another tenant's row, and for an action on a channel it is not listed on) |
| 409 | `conflict`, `idempotency_key_reused`, domain refusals such as `note_archived` |
| 413 | `payload_too_large` |
| 408 | `request_timeout` (a request body that never finished) |
| 422 | `invalid` (action input), `blocked_address` |
| 429 | `rate_limited`, `authentication_locked`; honour `Retry-After` |

## Idempotency

Send `Idempotency-Key` (1-128 characters of `A-Za-z0-9._:-`) on any action you may retry. The same
key with the same body replays the stored response and sets `Idempotent-Replayed: true`; the same
key with a different body is `409 idempotency_key_reused`. Keys are scoped to organization and
person and kept 24 hours. Stored responses are encrypted.

## Pagination

Classic list endpoints use page numbers: `?page=2&page_size=50` (default 50, maximum 200) and answer
`count`, `next`, `previous`, `results`. Actions that list use `limit` and `offset` and answer
`total`, `returned` and `next_offset` (null on the last page).

## Versioning and deprecation

The URL carries the major version (`/api/v1/`). Within a major version changes are additive: new
fields, new actions, new optional parameters. Something being retired answers with
`Deprecation: true` and a `Link: <successor>; rel="successor-version"` header for at least one
release, and the CHANGELOG says when it goes. The password-only JSON sign-in
(`/api/v1/auth/login/`) is off by default (`LEGACY_LOGIN_ENABLED`); use the allauth endpoints.

## Rate limits

Per client address (anonymous and signed-in), per credential and minute for actions
(`ACTIONS_RATE_*`), per address for MCP. `429` carries `Retry-After`. Authentication failures are
counted per key id and address, and per address overall, so one sender cannot lock an owner out.

## Tenancy

Sessions choose the organization with `X-Organization-ID`; keys and tokens are fixed to one. A row
of another tenant is `404`, never `403`: the API does not confirm it exists.

## Time and ids

Timestamps are ISO 8601 in UTC. Ids are UUIDs. Money and quantities are strings or integers as the
resource documents; never floats.
