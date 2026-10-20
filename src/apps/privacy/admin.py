from django.contrib import admin

from apps.common.admin import AuditedAdminMixin
from apps.privacy.models import (
    ConsentRecord,
    DataSubjectRequest,
    PersonalDataIncident,
    PrivacyNotice,
    ProcessingPurpose,
)


@admin.register(ProcessingPurpose)
class ProcessingPurposeAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "lawful_basis", "retention_days", "active")
    list_filter = ("lawful_basis", "active")
    search_fields = ("code", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PrivacyNotice)
class PrivacyNoticeAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("version", "effective_at", "active", "checksum_sha256")
    list_filter = ("active",)
    readonly_fields = ("created_at", "updated_at")


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
    )

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: object, obj: object = None) -> bool:
        return False


@admin.register(DataSubjectRequest)
class DataSubjectRequestAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "requester", "request_type", "status", "target_due_at", "created_at")
    list_filter = ("request_type", "status", "target_due_at")
    search_fields = ("id", "requester__email")
    readonly_fields = (
        "id",
        "requester",
        "request_type",
        "details",
        "target_due_at",
        "created_at",
        "updated_at",
    )

    def has_delete_permission(self, request: object, obj: object = None) -> bool:
        return False


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

    def has_delete_permission(self, request: object, obj: object = None) -> bool:
        # Incident records must be kept for at least five years.
        return False
