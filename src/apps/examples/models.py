"""Reference resource: delete this app when you start your product (docs: adding-an-action).

``Note`` exists to show every extension point in one small place: a tenant-scoped model, an
encrypted column, services shared by REST and actions, and (later phases) a flow, a webhook
event and a personal-data classification.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.encryption import EncryptedTextField
from apps.organizations.models import OrganizationScopedModel


class Note(OrganizationScopedModel):
    title = models.CharField(max_length=200)
    body = EncryptedTextField(blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta(OrganizationScopedModel.Meta):
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.title
