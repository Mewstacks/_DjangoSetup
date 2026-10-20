from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.flows.declare import job


@job("webhooks.dispatch_due", schedule="* * * * *")
def dispatch_due() -> dict[str, Any]:
    """Deliver pending webhooks whose time has come (the only deliverer when Temporal is off)."""
    from apps.webhooks.services import dispatch_due as run

    return dict(run())


@job("webhooks.prune", schedule="0 5 * * *")
def prune() -> dict[str, Any]:
    """Delete events (and their deliveries) older than 30 days."""
    from apps.webhooks.models import WebhookEvent

    deleted, _ = WebhookEvent.objects.filter(
        created_at__lt=timezone.now() - timedelta(days=30)
    ).delete()
    return {"deleted": deleted}
