from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from typing import Any, NoReturn

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase

from apps.common.models import AppendOnlyQuerySet

SENSITIVE_METADATA_KEYS = {
    "address",
    "authorization",
    "birth_date",
    "cnpj",
    "cookie",
    "cpf",
    "document",
    "email",
    "full_name",
    "ip_address",
    "name",
    "password",
    "phone",
    "secret",
    "token",
}


def _find_sensitive_keys(value: Any) -> set[str]:
    forbidden: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized in SENSITIVE_METADATA_KEYS:
                forbidden.add(normalized)
            forbidden.update(_find_sensitive_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            forbidden.update(_find_sensitive_keys(child))
    return forbidden


def validate_metadata(value: dict[str, object]) -> None:
    if not isinstance(value, dict):
        raise ValidationError("Audit metadata must be a JSON object.")
    forbidden = _find_sensitive_keys(value)
    if forbidden:
        raise ValidationError(f"Audit metadata contains forbidden keys: {sorted(forbidden)}")


class AuditEvent(models.Model):
    objects = AppendOnlyQuerySet.as_manager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=120, db_index=True)
    target_type = models.CharField(max_length=120, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    success = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True, validators=[validate_metadata])

    class Meta:
        ordering = ("-occurred_at",)
        indexes = [
            models.Index(fields=("organization", "occurred_at")),
            models.Index(fields=("actor", "occurred_at")),
            models.Index(fields=("action", "occurred_at")),
        ]

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding:
            raise ValidationError("Audit events are append-only.")
        # Uniqueness and constraint validation would add a SELECT per event on the
        # authentication hot path. The primary key is a client-side UUID and the
        # database still enforces both, so only the field validators are worth running.
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(self, using: Any | None = None, keep_parents: bool = False) -> NoReturn:
        raise ValidationError("Audit events cannot be deleted through the application.")

    def __str__(self) -> str:
        return f"{self.occurred_at} {self.action}"
