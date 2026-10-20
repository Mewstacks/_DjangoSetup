from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import timedelta
from typing import Any, NoReturn

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase
from django.utils import timezone

from apps.common.encryption import EncryptedTextField
from apps.common.models import AppendOnlyQuerySet, UUIDTimeStampedModel


def privacy_request_target() -> object:
    return timezone.now() + timedelta(days=settings.PRIVACY_REQUEST_TARGET_DAYS)


def incident_retention_target() -> object:
    now = timezone.now()
    try:
        return now.replace(year=now.year + 5)
    except ValueError:
        return now.replace(month=2, day=28, year=now.year + 5)


class ProcessingPurpose(UUIDTimeStampedModel):
    class LawfulBasis(models.TextChoices):
        CONSENT = "consent", "Consent"
        LEGAL_OBLIGATION = "legal_obligation", "Legal or regulatory obligation"
        CONTRACT = "contract", "Contract performance"
        LEGITIMATE_INTEREST = "legitimate_interest", "Legitimate interest"
        EXERCISE_OF_RIGHTS = "exercise_of_rights", "Exercise of rights"
        CREDIT_PROTECTION = "credit_protection", "Credit protection"
        LIFE_PROTECTION = "life_protection", "Protection of life"
        HEALTH = "health", "Protection of health"
        RESEARCH = "research", "Research"
        PUBLIC_POLICY = "public_policy", "Public policy"

    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField()
    lawful_basis = models.CharField(max_length=32, choices=LawfulBasis.choices)
    data_categories = models.JSONField(default=list)
    retention_days = models.PositiveIntegerField()
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.name


class PrivacyNotice(UUIDTimeStampedModel):
    version = models.CharField(max_length=32, unique=True)
    document_url = models.URLField()
    checksum_sha256 = models.CharField(max_length=64)
    effective_at = models.DateTimeField()
    active = models.BooleanField(default=False)

    class Meta:
        ordering = ("-effective_at",)

    def __str__(self) -> str:
        return self.version


class ConsentRecord(models.Model):
    objects = AppendOnlyQuerySet.as_manager()

    class Decision(models.TextChoices):
        GRANTED = "granted", "Granted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="consent_records",
    )
    purpose = models.ForeignKey(
        ProcessingPurpose,
        on_delete=models.PROTECT,
        related_name="consent_records",
    )
    notice = models.ForeignKey(
        PrivacyNotice,
        on_delete=models.PROTECT,
        related_name="consent_records",
    )
    decision = models.CharField(max_length=16, choices=Decision.choices)
    source = models.CharField(max_length=32, default="api")
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    evidence = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-recorded_at",)
        indexes = [
            models.Index(fields=("user", "purpose", "recorded_at")),
        ]

    def clean(self) -> None:
        if self.purpose_id and self.purpose.lawful_basis != ProcessingPurpose.LawfulBasis.CONSENT:
            raise ValidationError("Consent records are only valid for consent-based purposes.")

    def __str__(self) -> str:
        return f"{self.user_id}: {self.purpose_id} {self.decision}"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding:
            raise ValidationError("Consent records are append-only.")
        self.full_clean()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(self, using: Any | None = None, keep_parents: bool = False) -> NoReturn:
        raise ValidationError("Consent records cannot be deleted through the application.")


class DataSubjectRequest(UUIDTimeStampedModel):
    class RequestType(models.TextChoices):
        CONFIRMATION = "confirmation", "Confirmation of processing"
        ACCESS = "access", "Access"
        CORRECTION = "correction", "Correction"
        ANONYMIZATION = "anonymization", "Anonymization"
        BLOCKING = "blocking", "Blocking"
        DELETION = "deletion", "Deletion"
        PORTABILITY = "portability", "Portability"
        CONSENT_WITHDRAWAL = "consent_withdrawal", "Consent withdrawal"
        SHARING_INFORMATION = "sharing_information", "Sharing information"
        AUTOMATED_REVIEW = "automated_review", "Automated decision review"
        OPPOSITION = "opposition", "Opposition"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        VERIFYING = "verifying", "Verifying identity"
        IN_PROGRESS = "in_progress", "In progress"
        LEGAL_REVIEW = "legal_review", "Legal review"
        COMPLETED = "completed", "Completed"
        DENIED = "denied", "Denied"
        CANCELLED = "cancelled", "Cancelled"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="data_subject_requests",
    )
    request_type = models.CharField(max_length=32, choices=RequestType.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED)
    details = EncryptedTextField(blank=True)
    response_summary = EncryptedTextField(blank=True)
    target_due_at = models.DateTimeField(default=privacy_request_target, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    denial_reason_code = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "target_due_at")),
            models.Index(fields=("requester", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.id} ({self.request_type})"


class PersonalDataIncident(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        INVESTIGATING = "investigating", "Investigating"
        CONTAINED = "contained", "Contained"
        NOTIFYING = "notifying", "Notifying"
        CLOSED = "closed", "Closed"

    reference = models.CharField(max_length=40, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INVESTIGATING,
    )
    discovered_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    contains_personal_data = models.BooleanField(default=False)
    relevant_risk_or_harm = models.BooleanField(default=False)
    summary = EncryptedTextField()
    risk_assessment = EncryptedTextField(blank=True)
    data_categories = models.JSONField(default=list)
    approximate_subject_count = models.PositiveBigIntegerField(null=True, blank=True)
    notification_deadline_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set after legal review; ANPD Resolution 15/2024 generally uses 3 business days.",
    )
    anpd_notified_at = models.DateTimeField(null=True, blank=True)
    subjects_notified_at = models.DateTimeField(null=True, blank=True)
    retain_until = models.DateTimeField(default=incident_retention_target, db_index=True)

    class Meta:
        ordering = ("-discovered_at",)

    def clean(self) -> None:
        minimum = self.discovered_at + timedelta(days=5 * 365)
        if self.retain_until < minimum:
            raise ValidationError(
                "Personal-data incident records must be retained for at least 5 years."
            )

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        self.full_clean()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def __str__(self) -> str:
        return self.reference
