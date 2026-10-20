from __future__ import annotations

from django.db import models

from apps.common.models import UUIDTimeStampedModel


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
