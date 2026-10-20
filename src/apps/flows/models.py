from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.encryption import EncryptedTextField
from apps.common.models import UUIDTimeStampedModel


class FlowRun(UUIDTimeStampedModel):
    """The platform's own record of a flow execution, whichever engine ran it.

    Temporal remains the source of truth for a Temporal run; this row is what lets the API list
    runs per organization without querying Temporal's visibility store, and what the local
    engine executes against. Input and result are encrypted and kept short: flows pass ids and
    references, not documents.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    flow = models.CharField(max_length=120, db_index=True)
    engine = models.CharField(max_length=16)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.CASCADE
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    workflow_id = models.CharField(max_length=200, blank=True, db_index=True)
    temporal_run_id = models.CharField(max_length=64, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    input_json = EncryptedTextField(blank=True)
    result_json = EncryptedTextField(blank=True)
    error = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("organization", "-created_at")),
            models.Index(fields=("flow", "status")),
        ]

    @property
    def is_finished(self) -> bool:
        return self.status in {self.Status.COMPLETED, self.Status.FAILED, self.Status.CANCELLED}

    def __str__(self) -> str:
        return f"{self.flow} {self.status}"
