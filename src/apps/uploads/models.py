from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.organizations.models import OrganizationScopedModel


def upload_path(instance: UploadedFile, filename: str) -> str:
    # Neither the client's name nor its extension reaches the storage key.
    return f"uploads/{instance.organization_id}/{uuid.uuid4().hex}"


class UploadedFile(OrganizationScopedModel):
    class ScanStatus(models.TextChoices):
        CLEAN = "clean"
        SKIPPED = "skipped"  # no scanner configured

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    file = models.FileField(upload_to=upload_path, max_length=255)
    original_name = models.CharField(max_length=120)
    content_type = models.CharField(max_length=120)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    scan_status = models.CharField(max_length=10, choices=ScanStatus.choices)

    class Meta(OrganizationScopedModel.Meta):
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.original_name
