from apps.privacy.catalog import Category, not_personal, personal
from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEvent

not_personal(WebhookEndpoint, "A receiver URL and its signing secret (encrypted); no person.")
not_personal(WebhookDelivery, "Delivery bookkeeping: status codes and counters.")
personal(
    WebhookEvent,
    resolver=None,
    fields={"payload_json": Category.CONTENT},
    purpose="product-content",
    retention_field="created_at",
    on_erase="delete",
    reason="Thin events (ids) kept 30 days by webhooks.prune; not indexed per person.",
)
