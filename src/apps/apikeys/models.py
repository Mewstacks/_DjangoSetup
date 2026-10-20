"""Long-lived credentials for machines: scripts, integrations and AI agents.

A key looks like ``<prefix>_<public_id>_<secret>``. Only a keyed hash of the secret
(``blind_index``) is stored, so a database leak does not yield usable keys, and the secret is
shown exactly once at creation. The *role* is never copied into the key: it is read from the
owner's live membership on every call, so demoting someone takes effect on their next request,
not when the key is eventually reissued.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase
from django.utils import timezone

from apps.common.encryption import blind_index
from apps.organizations.models import OrganizationScopedModel

BLIND_INDEX_NAMESPACE = "api-key-v1"


def key_prefix() -> str:
    return str(getattr(settings, "API_KEY_PREFIX", "key"))


class ApiKey(OrganizationScopedModel):
    class Kind(models.TextChoices):
        API = "api", "API"
        AGENT = "agent", "AI agent"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys"
    )
    label = models.CharField(max_length=120)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.API)
    public_id = models.CharField(max_length=24, unique=True, editable=False)
    secret_index = models.CharField(max_length=64, editable=False)
    scopes = models.JSONField(default=list)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    allowed_ips = models.JSONField(default=list, blank=True)

    class Meta(OrganizationScopedModel.Meta):
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("organization", "created_at")),
            models.Index(fields=("user", "revoked_at")),
        ]

    def __str__(self) -> str:
        return self.label

    def clean(self) -> None:
        from apps.actions.registry import known_scopes

        unknown = set(self.scopes) - known_scopes()
        if unknown:
            raise ValidationError(f"Unknown scopes: {', '.join(sorted(unknown))}")
        if not self.scopes:
            raise ValidationError("A key needs at least one scope.")

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self._state.adding:
            self.clean()  # scopes are validated when the key is made, not on every touch
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @classmethod
    def issue(
        cls,
        *,
        user: Any,
        organization: Any,
        label: str,
        scopes: Iterable[str],
        kind: str = Kind.API,
        expires_at: Any = None,
        allowed_ips: Iterable[str] = (),
    ) -> tuple[ApiKey, str]:
        public_id = secrets.token_hex(8)
        secret = secrets.token_hex(32)
        key = cls.objects.create(
            user=user,
            organization=organization,
            label=label.strip()[:120] or "Key",
            kind=kind,
            public_id=public_id,
            secret_index=cls.index_for(secret),
            scopes=sorted(set(scopes)),
            expires_at=expires_at,
            allowed_ips=list(allowed_ips),
        )
        return key, f"{key_prefix()}_{public_id}_{secret}"

    @staticmethod
    def index_for(secret: str) -> str:
        return blind_index(secret, namespace=BLIND_INDEX_NAMESPACE)

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > timezone.now()

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at", "updated_at"])

    def rotate(self, *, overlap: timedelta = timedelta(hours=24)) -> tuple[ApiKey, str]:
        """Issue a successor with the same scopes; this key keeps working for ``overlap``.

        The overlap lets a deployment pick up the new secret without an outage; it never
        extends a key that was already going to expire sooner.
        """
        fresh, raw = ApiKey.issue(
            user=self.user,
            organization=self.organization,
            label=self.label,
            scopes=self.scopes,
            kind=self.kind,
            expires_at=self.expires_at,
            allowed_ips=self.allowed_ips,
        )
        cutoff = timezone.now() + overlap
        if self.expires_at is None or self.expires_at > cutoff:
            self.expires_at = cutoff
            self.save(update_fields=["expires_at", "updated_at"])
        return fresh, raw
