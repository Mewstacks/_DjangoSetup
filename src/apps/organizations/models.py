from __future__ import annotations

from collections.abc import Iterable

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.base import ModelBase

from apps.common.models import UUIDTimeStampedModel

slug_validator = RegexValidator(
    regex=r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$",
    message="Use 3-63 lowercase letters, numbers, or internal hyphens.",
)


class Organization(UUIDTimeStampedModel):
    name = models.CharField(max_length=160)
    slug = models.CharField(max_length=63, unique=True, validators=[slug_validator])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        self.slug = self.slug.strip().casefold()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def __str__(self) -> str:
        return self.name


class Membership(UUIDTimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Administrator"
        MEMBER = "member", "Member"
        BILLING = "billing", "Billing"
        AUDITOR = "auditor", "Auditor"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "user"),
                name="unique_organization_membership",
            )
        ]
        indexes = [
            models.Index(fields=("user", "is_active")),
            models.Index(fields=("organization", "role", "is_active")),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.organization_id} ({self.role})"


class OrganizationScopedModel(UUIDTimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

    class Meta:
        abstract = True
        indexes = [models.Index(fields=("organization", "created_at"))]
