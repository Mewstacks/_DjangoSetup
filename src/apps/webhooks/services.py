"""Emitting events and delivering them: outbox, signature, retries, circuit breaker.

Delivery is at-least-once. The event id is stable across attempts (``X-Webhook-Id``), so a
receiver deduplicates on it. Failures are retried with backoff for about a day, then the
delivery is marked ``dead``; an endpoint that fails ``WEBHOOK_DISABLE_AFTER`` times in a row is
switched off, so a decommissioned receiver stops costing a retry storm.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import timedelta
from typing import Any

import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.common.exceptions import DomainError, Invalid
from apps.common.netguard import post, validate_url
from apps.webhooks.events import EVENT_TYPES
from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEvent

logger = structlog.get_logger("apps.webhooks")
BACKOFF = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(hours=6),
    timedelta(hours=24),
)
MAX_ATTEMPTS = len(BACKOFF) + 1
LOCK = timedelta(minutes=2)


def sign(secret: str, timestamp: int, body: bytes) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    return mac.hexdigest()


def signature_header(secrets_in_use: list[str], timestamp: int, body: bytes) -> str:
    """``v1=<hex>`` per active secret, space separated, so rotation never breaks a receiver."""
    return " ".join(f"v1={sign(s, timestamp, body)}" for s in secrets_in_use)


def validate_endpoint_url(url: str) -> None:
    try:
        validate_url(url)
    except DomainError as error:
        raise Invalid(str(error.detail), code="invalid_url") from error


def emit(event_type: str, organization: Any, data: dict[str, Any]) -> WebhookEvent | None:
    """Record an event for every subscribed endpoint. Call it inside the business transaction.

    The event and its deliveries are written with the change they describe, so a rollback
    removes them and a commit can never lose them (the transactional outbox pattern).
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown event type {event_type!r}; declare it with register_event().")
    endpoints = [
        e
        for e in WebhookEndpoint.objects.filter(organization=organization, is_active=True)
        if e.subscribed_to(event_type)
    ]
    if not endpoints:
        return None
    event = WebhookEvent.objects.create(
        organization=organization,
        event_type=event_type,
        payload_json=json.dumps(data, default=str),
    )
    deliveries = [
        WebhookDelivery(organization=organization, event=event, endpoint=endpoint)
        for endpoint in endpoints
    ]
    WebhookDelivery.objects.bulk_create(deliveries)
    transaction.on_commit(lambda: kick([d.pk for d in deliveries]))
    return event


def kick(delivery_ids: list[Any]) -> None:
    """Ask the flow engine to deliver right away; the dispatch job is the safety net."""
    if not settings.TEMPORAL_ENABLED:
        return  # the minute job picks them up; no network I/O on the request path
    from apps.flows.engine import get_engine

    for delivery_id in delivery_ids:
        try:
            get_engine().start(
                "webhooks.deliver",
                {"delivery_id": str(delivery_id)},
                workflow_id=f"webhook:{delivery_id}",
            )
        except Exception:
            logger.warning("webhook_kick_failed", delivery_id=str(delivery_id))


def _body(event: WebhookEvent) -> bytes:
    return json.dumps(
        {
            "id": str(event.pk),
            "type": event.event_type,
            "created": event.created_at.isoformat(),
            "organization_id": str(event.organization_id),
            "data": event.payload,
        },
        separators=(",", ":"),
    ).encode()


def _claim(delivery_id: Any) -> WebhookDelivery | None:
    """Take the delivery for ~2 minutes so the workflow and the job never both send it."""
    now = timezone.now()
    taken = (
        WebhookDelivery.objects.filter(
            pk=delivery_id, status=WebhookDelivery.Status.PENDING, next_attempt_at__lte=now
        )
        .exclude(locked_until__gt=now)
        .update(locked_until=now + LOCK)
    )
    if not taken:
        return None
    return WebhookDelivery.objects.select_related("endpoint", "event").get(pk=delivery_id)


def attempt(delivery_id: Any) -> dict[str, Any]:
    """One delivery attempt. Returns ``{"state": delivered|retry|dead|skipped}``."""
    delivery = _claim(delivery_id)
    if delivery is None:
        return {"state": "skipped"}
    endpoint = delivery.endpoint
    if not endpoint.is_active:
        delivery.status = WebhookDelivery.Status.DEAD
        delivery.last_error = "endpoint disabled"
        delivery.locked_until = None
        delivery.save(update_fields=["status", "last_error", "locked_until", "updated_at"])
        return {"state": "dead"}

    body = _body(delivery.event)
    timestamp = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Id": str(delivery.event_id),
        "X-Webhook-Timestamp": str(timestamp),
        "X-Webhook-Attempt": str(delivery.attempts + 1),
        "X-Webhook-Signature": signature_header(endpoint.secrets_for_signing(), timestamp, body),
    }
    delivery.attempts += 1
    ok, code, error = False, None, ""
    try:
        result = post(endpoint.url, body=body, headers=headers)
        code = result.status
        ok = 200 <= result.status < 300
        if not ok:
            error = f"HTTP {result.status}"
    except DomainError as failure:
        error = str(failure.detail)[:200]
    delivery.last_status_code, delivery.last_error = code, error
    delivery.locked_until = None
    if ok:
        delivery.status = WebhookDelivery.Status.DELIVERED
        delivery.delivered_at = timezone.now()
        endpoint.failure_streak = 0
    else:
        endpoint.failure_streak += 1
        if delivery.attempts >= MAX_ATTEMPTS:
            delivery.status = WebhookDelivery.Status.DEAD
        else:
            delivery.next_attempt_at = timezone.now() + BACKOFF[delivery.attempts - 1]
    delivery.save()
    if not ok and endpoint.failure_streak >= settings.WEBHOOK_DISABLE_AFTER:
        endpoint.is_active = False
        endpoint.disabled_reason = "too_many_failures"
        record_event(
            action="webhook.endpoint_disabled",
            organization=endpoint.organization,
            target=endpoint,
            metadata={"reason": "too_many_failures"},
        )
    endpoint.save(update_fields=["failure_streak", "is_active", "disabled_reason", "updated_at"])
    state = "delivered" if ok else ("dead" if delivery.status == "dead" else "retry")
    return {"state": state, "attempts": delivery.attempts}


def dispatch_due(limit: int = 200) -> dict[str, int]:
    """Deliver everything whose time has come. The minute job, and the local engine's worker."""
    now = timezone.now()
    due = list(
        WebhookDelivery.objects.filter(
            status=WebhookDelivery.Status.PENDING, next_attempt_at__lte=now
        )
        .exclude(locked_until__gt=now)
        .order_by("next_attempt_at")
        .values_list("pk", flat=True)[:limit]
    )
    counts = {"delivered": 0, "retry": 0, "dead": 0, "skipped": 0}
    for delivery_id in due:
        counts[attempt(delivery_id)["state"]] += 1
    return counts


def redeliver(delivery: WebhookDelivery) -> None:
    delivery.status = WebhookDelivery.Status.PENDING
    delivery.attempts = 0
    delivery.next_attempt_at = timezone.now()
    delivery.locked_until = None
    delivery.save(
        update_fields=["status", "attempts", "next_attempt_at", "locked_until", "updated_at"]
    )
    transaction.on_commit(lambda: kick([delivery.pk]))
