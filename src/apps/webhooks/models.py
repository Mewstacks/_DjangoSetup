from __future__ import annotations

import json
import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.encryption import EncryptedTextField
from apps.organizations.models import OrganizationScopedModel


def new_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


class WebhookEndpoint(OrganizationScopedModel):
    url = models.URLField(max_length=500)
    description = models.CharField(max_length=200, blank=True)
    events = models.JSONField(default=list, help_text="Event types, or ['*'] for all.")
    secret = EncryptedTextField()
    previous_secret = EncryptedTextField(blank=True)
    previous_secret_expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    failure_streak = models.PositiveIntegerField(default=0)
    disabled_reason = models.CharField(max_length=80, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta(OrganizationScopedModel.Meta):
        ordering = ("-created_at",)

    def subscribed_to(self, event_type: str) -> bool:
        return "*" in self.events or event_type in self.events

    def secrets_for_signing(self) -> list[str]:
        """The current secret, plus the previous one while its overlap window is open."""
        active = [self.secret]
        if (
            self.previous_secret
            and self.previous_secret_expires_at
            and self.previous_secret_expires_at > timezone.now()
        ):
            active.append(self.previous_secret)
        return active

    def rotate(self, overlap: timedelta = timedelta(hours=24)) -> str:
        fresh = new_secret()
        self.previous_secret = self.secret
        self.previous_secret_expires_at = timezone.now() + overlap
        self.secret = fresh
        self.save(
            update_fields=["secret", "previous_secret", "previous_secret_expires_at", "updated_at"]
        )
        return fresh

    def __str__(self) -> str:
        return self.url


class WebhookEvent(OrganizationScopedModel):
    """The outbox row: written in the same transaction as the change it announces."""

    event_type = models.CharField(max_length=120, db_index=True)
    payload_json = EncryptedTextField()

    class Meta(OrganizationScopedModel.Meta):
        ordering = ("-created_at",)

    @property
    def payload(self) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads(self.payload_json) if self.payload_json else {}
        return loaded


class WebhookDelivery(OrganizationScopedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        DEAD = "dead", "Gave up"

    event = models.ForeignKey(WebhookEvent, on_delete=models.CASCADE, related_name="deliveries")
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta(OrganizationScopedModel.Meta):
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("status", "next_attempt_at"))]
