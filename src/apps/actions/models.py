from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.encryption import EncryptedTextField
from apps.common.models import UUIDTimeStampedModel
from apps.organizations.models import OrganizationScopedModel


class IdempotencyRecord(UUIDTimeStampedModel):
    """One claimed ``Idempotency-Key``.

    The row is created inside the same transaction as the action it protects, so a failure
    rolls the claim back and a retry runs again, while a concurrent duplicate blocks on the
    unique index until the first call commits and then replays its stored response. A table,
    not the cache: the guarantee must survive a cache flush and cannot be evicted.

    Scoped by organization *and* actor: two people in one tenant choosing the same key must
    never receive each other's response.
    """

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    actor_id = models.UUIDField()
    key = models.CharField(max_length=128)
    action = models.CharField(max_length=120)
    request_hash = models.CharField(max_length=64)
    response = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "actor_id", "key"), name="unique_idempotency_key"
            )
        ]
        indexes = [models.Index(fields=("created_at",))]


class AgentRun(OrganizationScopedModel):
    """One stretch of an agent working through MCP - the AI-time ledger.

    ``duration_ms`` is the span between the first and the last call the *server* received.
    That is activity on this platform, not the model's thinking time: the server cannot see
    inside the client. It is still the only AI time that is measured instead of claimed. The
    model name and token counts are what the agent *reported*, kept apart and unverified.
    """

    credential_id = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_runs"
    )
    started_at = models.DateTimeField(default=timezone.now)
    last_call_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    tool_calls = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True)
    reported_model = models.CharField(max_length=80, blank=True)
    reported_input_tokens = models.PositiveIntegerField(null=True, blank=True)
    reported_output_tokens = models.PositiveIntegerField(null=True, blank=True)

    class Meta(OrganizationScopedModel.Meta):
        ordering = ("-started_at",)
        indexes = [
            models.Index(fields=("organization", "-started_at")),
            models.Index(fields=("credential_id", "ended_at")),
        ]

    @property
    def is_open(self) -> bool:
        return self.ended_at is None


class ActionJournal(OrganizationScopedModel):
    """What a write changed, in enough detail to take it back.

    ``AuditEvent`` states that something happened and may not carry data; this row keeps the
    before/after snapshot an undo needs, so it holds personal data and is purged on a
    schedule (``ACTIONS_JOURNAL_RETENTION_DAYS``) rather than kept like the audit trail.
    """

    class Op(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        ARCHIVE = "archive", "Archive"
        DELETE = "delete", "Delete"

    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        UNDONE = "undone", "Undone"

    run = models.ForeignKey(
        AgentRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="changes"
    )
    credential_id = models.CharField(max_length=64, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="action_journal"
    )
    action = models.CharField(max_length=120)
    op = models.CharField(max_length=8, choices=Op.choices)
    target_type = models.CharField(max_length=120)
    target_id = models.CharField(max_length=64)
    label = models.CharField(max_length=200, blank=True)
    # Snapshots hold business data (including columns that are encrypted at rest elsewhere), so
    # they are encrypted here too; the properties below hide the JSON round trip.
    before_json = EncryptedTextField(blank=True)
    after_json = EncryptedTextField(blank=True)
    dedupe_key = models.CharField(max_length=120, blank=True, db_index=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.APPLIED)
    undone_at = models.DateTimeField(null=True, blank=True)

    class Meta(OrganizationScopedModel.Meta):
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("organization", "-created_at")),
            models.Index(fields=("target_type", "target_id")),
        ]

    @property
    def before(self) -> dict[str, Any]:
        return json.loads(self.before_json) if self.before_json else {}

    @before.setter
    def before(self, value: dict[str, Any]) -> None:
        self.before_json = json.dumps(value, default=str)

    @property
    def after(self) -> dict[str, Any]:
        return json.loads(self.after_json) if self.after_json else {}

    @after.setter
    def after(self, value: dict[str, Any]) -> None:
        self.after_json = json.dumps(value, default=str)
