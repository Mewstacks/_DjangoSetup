# Webhooks

Outbound events with a transactional outbox: an event is written in the same transaction as the
change it announces, so a rollback never sends it and a commit never loses it.

```python
# <app>/events.py
register_event("order.paid", "An order was paid. Data: order_id.")
# inside the transaction that changes the order
emit("order.paid", ctx.organization, {"order_id": str(order.id)})
```

Events are **thin**: ids, not documents. A receiver fetches data with its own credentials.

## Receiving

Headers: `X-Webhook-Id` (stable across retries: deduplicate on it), `X-Webhook-Timestamp`,
`X-Webhook-Signature: v1=<hex>` where the value is HMAC-SHA256 of `"<timestamp>.<body>"` with the
endpoint secret. Reject timestamps older than a few minutes. During secret rotation two
signatures are sent (space separated); accept either.

## Managing

`/api/v1/webhooks/endpoints/` (owners/admins): create (secret returned once), update, rotate
(`rotate-secret`), send a test (`test`). `/api/v1/webhooks/deliveries/` lists history and
`redeliver`s. Endpoints must be https and resolve to public addresses.

## Delivery

Workflow with backoff 1m, 5m, 30m, 2h, 6h, 24h (or the `webhooks.dispatch_due` job when Temporal
is off). A claim lock prevents double sends. After `WEBHOOK_DISABLE_AFTER` consecutive failures
the endpoint is switched off and an audit event is recorded.

## SSRF protection

`apps.common.netguard` is used for every outbound call: https only, every resolved address must
be public, the connection goes to the validated IP (no DNS rebinding), redirects are never
followed, responses are size-bounded.
