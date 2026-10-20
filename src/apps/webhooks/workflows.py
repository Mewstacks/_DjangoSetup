"""Temporal delivery of one webhook: retries with backoff, one workflow per delivery."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import BaseModel
from temporalio import workflow

from apps.flows.sdk import flow

ATTEMPT_ACTIVITY = "webhooks.attempt"
MAX_ATTEMPTS = 7
BACKOFF_MINUTES = (1, 5, 30, 120, 360, 1440)


class DeliveryInput(BaseModel):
    delivery_id: str


def run_delivery_local(payload: dict[str, Any]) -> dict[str, Any]:
    from apps.webhooks.services import attempt

    return attempt(payload["delivery_id"])


@flow("webhooks.deliver", input=DeliveryInput, local=run_delivery_local)
class DeliverWebhook:
    """Deliver one webhook, retrying with backoff for about a day."""

    @workflow.run
    async def run(self, data: DeliveryInput) -> dict[str, Any]:
        result: dict[str, Any] = {"state": "retry"}
        for number in range(MAX_ATTEMPTS):
            result = await workflow.execute_activity(
                ATTEMPT_ACTIVITY,
                data,
                result_type=dict,
                start_to_close_timeout=timedelta(seconds=60),
            )
            if result["state"] in ("delivered", "dead", "skipped"):
                return result
            if number < len(BACKOFF_MINUTES):
                await workflow.sleep(timedelta(minutes=BACKOFF_MINUTES[number]))
        return result
