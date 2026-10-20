from __future__ import annotations

from typing import Any

from temporalio import activity

from apps.flows.declare import activity as register_activity
from apps.webhooks.workflows import ATTEMPT_ACTIVITY, DeliveryInput


@register_activity
@activity.defn(name=ATTEMPT_ACTIVITY)
def attempt_delivery(data: DeliveryInput) -> dict[str, Any]:
    from apps.webhooks.models import WebhookDelivery
    from apps.webhooks.services import attempt

    # The workflow sleeps between attempts itself; make the row due so the claim succeeds.
    WebhookDelivery.objects.filter(pk=data.delivery_id).update(next_attempt_at=_now())
    return attempt(data.delivery_id)


def _now() -> Any:
    from django.utils import timezone

    return timezone.now()
