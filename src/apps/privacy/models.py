from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from datetime import timedelta
from typing import Any, NoReturn

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.base import ModelBase
from django.utils import timezone

from apps.common.encryption import (
    EncryptedTextField,
    blind_index,
    blind_index_candidates,
    chain_digest,
)
from apps.common.models import AppendOnlyQuerySet, UUIDTimeStampedModel

GENESIS = "0" * 64


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

    class CookieCategory(models.TextChoices):
        NONE = "", "Not a cookie purpose"
        NECESSARY = "necessary", "Strictly necessary"
        PREFERENCES = "preferences", "Preferences"
        ANALYTICS = "analytics", "Analytics"
        MARKETING = "marketing", "Marketing"

    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField()
    lawful_basis = models.CharField(max_length=32, choices=LawfulBasis.choices)
    data_categories = models.JSONField(default=list)
    retention_days = models.PositiveIntegerField()
    active = models.BooleanField(default=True)
    # Art. 14: processing of children's data needs the specific, prominent consent of a parent
    # or guardian. A purpose that involves children makes the API ask for that confirmation.
    involves_children = models.BooleanField(default=False)
    # Art. 18 VIII: what happens if the person says no. Shown wherever consent is asked.
    refusal_consequence = models.TextField(blank=True)
    cookie_category = models.CharField(
        max_length=16, choices=CookieCategory.choices, blank=True, default=""
    )

    class Meta:
        ordering = ("code",)

    def digest(self) -> str:
        """What a consent actually attested to: change any of this and the digest changes."""
        body = json.dumps(
            [self.code, self.description, self.lawful_basis, sorted(self.data_categories)],
            sort_keys=True,
        )
        return hashlib.sha256(body.encode()).hexdigest()

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

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """A notice, once written, only ever changes by being switched off.

        Consents reference it by id and record its checksum; editing the text, URL or version in
        place would change what every earlier consent appears to have agreed to. Publish a new
        version instead. At most one notice is active: activating one retires the others.
        """
        with transaction.atomic():
            if not self._state.adding:
                stored = type(self).objects.get(pk=self.pk)
                frozen = ("version", "document_url", "checksum_sha256", "effective_at")
                if any(getattr(stored, name) != getattr(self, name) for name in frozen):
                    raise ValidationError("A privacy notice is immutable; publish a new version.")
            if self.active:
                type(self).objects.exclude(pk=self.pk).filter(active=True).update(active=False)
            super().save(
                force_insert=force_insert,
                force_update=force_update,
                using=using,
                update_fields=update_fields,
            )

    def __str__(self) -> str:
        return self.version


class DataSubject(UUIDTimeStampedModel):
    """A person whose data we hold, whether or not they have an account.

    Leads, contacts and people who only ever filled in a form have no ``User`` but have the
    same rights. The e-mail is stored encrypted, with a blind index for lookup; ``user`` links
    the record to an account when there is one.
    """

    email = EncryptedTextField()
    email_index = models.CharField(max_length=64, unique=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="data_subject",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
    anonymized_at = models.DateTimeField(null=True, blank=True)

    NAMESPACE = "data-subject-email-v1"

    @classmethod
    def index_for(cls, email: str) -> str:
        return blind_index(email, namespace=cls.NAMESPACE)

    @classmethod
    def for_email(cls, email: str) -> DataSubject:
        current, *older = blind_index_candidates(email, namespace=cls.NAMESPACE)
        subject = cls.objects.filter(email_index=current).first()
        if subject is None and older:
            subject = cls.objects.filter(email_index__in=older).first()
            if subject is not None:  # written under a key being rotated out
                subject.email_index = current
                subject.save(update_fields=["email_index", "updated_at"])
        if subject is None:
            subject, _ = cls.objects.get_or_create(
                email_index=current, defaults={"email": email.strip().casefold()}
            )
        return subject

    @classmethod
    def for_user(cls, user: Any) -> DataSubject:
        existing = cls.objects.filter(user=user).first()
        if existing is not None:
            return existing
        linked = cls.for_email(user.email)
        if linked.user_id is None:
            linked.user = user
            linked.verified_at = linked.verified_at or timezone.now()
            linked.save(update_fields=["user", "verified_at", "updated_at"])
        return linked

    def __str__(self) -> str:
        return str(self.pk)


class SubProcessor(UUIDTimeStampedModel):
    """A third party that processes personal data on our behalf, and where."""

    class Transfer(models.TextChoices):
        NONE = "none", "No international transfer"
        ADEQUACY = "adequacy", "Adequacy decision"
        STANDARD_CLAUSES = "standard_clauses", "Standard contractual clauses"
        BINDING_RULES = "binding_rules", "Binding corporate rules"
        CONSENT = "consent", "Specific consent"
        OTHER = "other", "Other legal basis (art. 33)"

    name = models.CharField(max_length=160)
    purpose = models.CharField(max_length=240)
    country = models.CharField(max_length=2, help_text="ISO 3166-1 alpha-2")
    transfer_mechanism = models.CharField(max_length=20, choices=Transfer.choices)
    data_categories = models.JSONField(default=list)
    contract_url = models.URLField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


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
    # What the person was shown, frozen at the time: editing a purpose later must not change
    # what this record proves.
    notice_checksum = models.CharField(max_length=64, blank=True)
    purpose_digest = models.CharField(max_length=64, blank=True)
    # A hash chain per user makes silent edits or deletions of a person's history detectable.
    seq = models.PositiveIntegerField(default=0)
    prev_hash = models.CharField(max_length=64, blank=True)
    hash = models.CharField(max_length=64, blank=True)

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

    def compute_hash(self) -> str:
        body = json.dumps(
            [
                str(self.id),
                str(self.user_id),
                str(self.purpose_id),
                str(self.notice_id),
                self.decision,
                self.source,
                self.notice_checksum,
                self.purpose_digest,
                self.evidence,
                self.seq,
                self.prev_hash,
            ],
            sort_keys=True,
            default=str,
        )
        return chain_digest("consent", body)

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
        with transaction.atomic():
            # Lock the person's row so two concurrent decisions cannot both extend the chain
            # from the same predecessor.
            type(self.user).objects.select_for_update().filter(pk=self.user_id).first()
            last = ConsentRecord.objects.filter(user_id=self.user_id).order_by("-seq").first()
            self.seq = (last.seq + 1) if last else 1
            self.prev_hash = last.hash if last and last.hash else GENESIS
            self.notice_checksum = self.notice_checksum or self.notice.checksum_sha256
            self.purpose_digest = self.purpose_digest or self.purpose.digest()
            self.hash = self.compute_hash()
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

    # The only ways a request may move. Anything else is a bug or an attempt to rewrite
    # history, so it raises instead of silently saving.
    TRANSITIONS: dict[str, frozenset[str]] = {
        "received": frozenset({"verifying", "in_progress", "denied", "cancelled"}),
        "verifying": frozenset({"in_progress", "denied", "cancelled"}),
        "in_progress": frozenset({"legal_review", "completed", "denied", "cancelled"}),
        "legal_review": frozenset({"in_progress", "completed", "denied"}),
        "completed": frozenset(),
        "denied": frozenset(),
        "cancelled": frozenset(),
    }
    TERMINAL = frozenset({"completed", "denied", "cancelled"})

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="data_subject_requests",
    )
    subject = models.ForeignKey(
        DataSubject,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="requests",
    )
    request_type = models.CharField(max_length=32, choices=RequestType.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED)
    details = EncryptedTextField(blank=True)
    response_summary = EncryptedTextField(blank=True)
    target_due_at = models.DateTimeField(default=privacy_request_target, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    denial_reason_code = models.CharField(max_length=80, blank=True)
    identity_verified_at = models.DateTimeField(null=True, blank=True)
    export_name = models.CharField(max_length=120, blank=True)
    export_expires_at = models.DateTimeField(null=True, blank=True)
    # The link is a bearer secret; it stops working after PRIVACY_EXPORT_MAX_DOWNLOADS uses.
    export_downloads = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "target_due_at")),
            models.Index(fields=("requester", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.id} ({self.request_type})"

    @property
    def is_terminal(self) -> bool:
        return self.status in self.TERMINAL

    def transition_to(self, new_status: str, *, summary: str = "", reason_code: str = "") -> None:
        """Move to ``new_status`` if the state machine allows it; stamp the side effects."""
        if new_status not in self.TRANSITIONS.get(self.status, frozenset()):
            raise ValidationError(f"A request cannot go from {self.status} to {new_status}.")
        if new_status == self.Status.DENIED and not reason_code:
            raise ValidationError("A denial needs a reason code.")
        self.status = new_status
        if summary:
            self.response_summary = summary
        if reason_code:
            self.denial_reason_code = reason_code
        if new_status in self.TERMINAL:
            self.completed_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "response_summary",
                "denial_reason_code",
                "completed_at",
                "updated_at",
            ]
        )

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding:
            stored = type(self).objects.filter(pk=self.pk).values("status").first()
            if stored and stored["status"] != self.status:
                allowed = self.TRANSITIONS.get(stored["status"], frozenset())
                if self.status not in allowed:
                    raise ValidationError(
                        f"A request cannot go from {stored['status']} to {self.status}."
                    )
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(self, using: Any | None = None, keep_parents: bool = False) -> NoReturn:
        raise ValidationError("Data subject requests are the proof of compliance; keep them.")


class LegalHold(UUIDTimeStampedModel):
    """Data about this person must be kept (litigation, a legal duty - LGPD art. 16, I)."""

    subject = models.ForeignKey(DataSubject, on_delete=models.PROTECT, related_name="holds")
    reason = EncryptedTextField()
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    @classmethod
    def active_for(cls, subject: DataSubject) -> bool:
        return cls.objects.filter(subject=subject, released_at__isnull=True).exists()

    def __str__(self) -> str:
        return f"hold on {self.subject_id}"


class PrivacyReminder(UUIDTimeStampedModel):
    """Remembers which deadline reminders were already sent, so a re-run never repeats them."""

    request = models.ForeignKey(
        DataSubjectRequest, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    incident = models.ForeignKey(
        "privacy.PersonalDataIncident",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    kind = models.CharField(max_length=32)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("request", "kind"),
                condition=models.Q(request__isnull=False),
                name="unique_request_reminder",
            ),
            models.UniqueConstraint(
                fields=("incident", "kind"),
                condition=models.Q(incident__isnull=False),
                name="unique_incident_reminder",
            ),
        ]


class CookieConsent(UUIDTimeStampedModel):
    """A visitor's cookie choice, kept as proof (LGPD art. 8 par. 2) without an account.

    ``visitor_id`` is a random identifier the front end mints and stores next to the choice; it
    is not an account and not an address. Each change of mind is a new row (the newest wins), so
    the history of what was asked and answered survives. No IP address is stored, only a keyed
    hash, as in the audit trail.
    """

    visitor_id = models.UUIDField(db_index=True)
    categories = models.JSONField(default=dict)  # {"analytics": true, "marketing": false}
    notice_checksum = models.CharField(max_length=64, blank=True)
    evidence = models.JSONField(default=dict, blank=True)  # ua_hash, ip_hash

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("visitor_id", "created_at"))]

    def __str__(self) -> str:
        return f"{self.visitor_id}"


class ImpactAssessment(UUIDTimeStampedModel):
    """A data protection impact assessment (RIPD, LGPD art. 38) for one processing operation.

    The ANPD may ask for it. It describes processing, not people, so it is not personal data.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        REVIEW_DUE = "review_due", "Review due"

    title = models.CharField(max_length=200)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    purpose = models.ForeignKey(
        ProcessingPurpose, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    processing_description = models.TextField()
    data_categories = models.JSONField(default=list)
    necessity = models.TextField(blank=True)
    risks = models.JSONField(
        default=list
    )  # [{"risk": "...", "likelihood": "...", "impact": "..."}]
    measures = models.TextField(blank=True)
    dpo_opinion = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    next_review_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        return self.title


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
    measures_taken = EncryptedTextField(blank=True)
    data_categories = models.JSONField(default=list)
    approximate_subject_count = models.PositiveBigIntegerField(null=True, blank=True)
    notification_deadline_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Computed from confirmation using PRIVACY_INCIDENT_BUSINESS_DAYS (ANPD Resolution "
            "CD/ANPD 15/2024 generally uses 3 business days). Confirm with legal counsel."
        ),
    )
    # The people affected are told within the same period as the ANPD (Res. CD/ANPD 15/2024).
    subjects_deadline_at = models.DateTimeField(null=True, blank=True)
    anpd_notified_at = models.DateTimeField(null=True, blank=True)
    # A first communication may be completed later: up to 20 business days after it.
    complement_deadline_at = models.DateTimeField(null=True, blank=True)
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
        if (
            self.confirmed_at
            and self.relevant_risk_or_harm
            and self.notification_deadline_at is None
        ):
            from apps.privacy.deadlines import add_business_days

            # Small processing agents get the period doubled (Res. CD/ANPD 15/2024).
            days = settings.PRIVACY_INCIDENT_BUSINESS_DAYS * (
                2 if settings.PRIVACY_SMALL_AGENT else 1
            )
            self.notification_deadline_at = add_business_days(self.confirmed_at, days)
            if self.subjects_deadline_at is None:
                self.subjects_deadline_at = self.notification_deadline_at
        if self.anpd_notified_at and self.complement_deadline_at is None:
            from apps.privacy.deadlines import add_business_days

            self.complement_deadline_at = add_business_days(
                self.anpd_notified_at, settings.PRIVACY_INCIDENT_COMPLEMENT_BUSINESS_DAYS
            )
        self.full_clean()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(self, using: Any | None = None, keep_parents: bool = False) -> NoReturn:
        raise ValidationError("Incident records must be kept for at least five years.")

    def __str__(self) -> str:
        return self.reference
