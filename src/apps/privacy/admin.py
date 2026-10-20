from __future__ import annotations

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.utils import timezone

from apps.common.admin import AuditedAdminMixin
from apps.common.exceptions import DomainError
from apps.privacy.models import (
    ConsentRecord,
    DataSubject,
    DataSubjectRequest,
    LegalHold,
    PersonalDataIncident,
    PrivacyNotice,
    ProcessingPurpose,
    SubProcessor,
)
from apps.privacy.services import finish_review


def _reason(error: Exception) -> str:
    if isinstance(error, DomainError):
        return str(error.detail)
    return str(getattr(error, "messages", [error])[0])


@admin.register(ProcessingPurpose)
class ProcessingPurposeAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "lawful_basis", "retention_days", "active", "involves_children")
    list_filter = ("lawful_basis", "active")
    search_fields = ("code", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PrivacyNotice)
class PrivacyNoticeAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("version", "effective_at", "active", "checksum_sha256")
    list_filter = ("active",)
    readonly_fields = ("created_at", "updated_at")

    def get_readonly_fields(
        self, request: HttpRequest, obj: PrivacyNotice | None = None
    ) -> tuple[str, ...]:
        # A notice is immutable once saved; only the active flag can change.
        base = ("created_at", "updated_at")
        if obj is not None:
            return (*base, "version", "document_url", "checksum_sha256", "effective_at")
        return base

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False


@admin.register(SubProcessor)
class SubProcessorAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "country", "transfer_mechanism", "active")
    list_filter = ("transfer_mechanism", "active")
    search_fields = ("name",)


@admin.register(DataSubject)
class DataSubjectAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "user", "verified_at", "blocked_at", "anonymized_at")
    readonly_fields = (
        "id",
        "email_index",
        "user",
        "verified_at",
        "blocked_at",
        "anonymized_at",
        "created_at",
        "updated_at",
    )
    exclude = ("email",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False


@admin.register(LegalHold)
class LegalHoldAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("subject", "placed_by", "created_at", "released_at")
    list_filter = ("released_at",)
    readonly_fields = ("placed_by", "created_at", "updated_at")
    actions = ("release",)

    def save_model(self, request: HttpRequest, obj: LegalHold, form: object, change: bool) -> None:
        if not change:
            obj.placed_by = request.user  # type: ignore[assignment]
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    @admin.action(description="Release the selected holds")
    def release(self, request: HttpRequest, queryset: object) -> None:
        queryset.filter(released_at__isnull=True).update(released_at=timezone.now())  # type: ignore[attr-defined]


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("recorded_at", "user", "purpose", "decision", "source")
    list_filter = ("decision", "purpose", "recorded_at")
    search_fields = ("user__email", "idempotency_key")
    readonly_fields = (
        "id",
        "idempotency_key",
        "user",
        "purpose",
        "notice",
        "decision",
        "source",
        "recorded_at",
        "evidence",
        "notice_checksum",
        "purpose_digest",
        "seq",
        "prev_hash",
        "hash",
    )

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: object, obj: object = None) -> bool:
        return False


@admin.register(DataSubjectRequest)
class DataSubjectRequestAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "request_type", "status", "target_due_at", "created_at")
    list_filter = ("request_type", "status", "target_due_at")
    search_fields = ("id",)
    readonly_fields = (
        "id",
        "requester",
        "subject",
        "request_type",
        "status",
        "details",
        "response_summary",
        "target_due_at",
        "completed_at",
        "denial_reason_code",
        "identity_verified_at",
        "export_name",
        "export_expires_at",
        "created_at",
        "updated_at",
    )
    actions = ("complete_review", "deny_review")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    @admin.action(description="Finish review: answered, complete the request")
    def complete_review(self, request: HttpRequest, queryset: object) -> None:
        for item in queryset:  # type: ignore[attr-defined]
            try:
                finish_review(item, outcome="completed", summary="Reviewed and answered.")
            except (DomainError, ValidationError) as error:
                self.message_user(request, f"{item.pk}: {_reason(error)}", messages.ERROR)

    @admin.action(description="Finish review: deny (legal basis to refuse)")
    def deny_review(self, request: HttpRequest, queryset: object) -> None:
        for item in queryset:  # type: ignore[attr-defined]
            try:
                finish_review(
                    item,
                    outcome="denied",
                    summary="The request could not be fulfilled.",
                    reason_code="legal_basis_to_refuse",
                )
            except (DomainError, ValidationError) as error:
                self.message_user(request, f"{item.pk}: {_reason(error)}", messages.ERROR)


@admin.register(PersonalDataIncident)
class PersonalDataIncidentAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = (
        "reference",
        "status",
        "discovered_at",
        "contains_personal_data",
        "relevant_risk_or_harm",
        "notification_deadline_at",
    )
    list_filter = ("status", "contains_personal_data", "relevant_risk_or_harm")
    search_fields = ("reference",)
    readonly_fields = ("created_at", "updated_at", "retain_until")

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        # Incident records must be kept for at least five years.
        return False
