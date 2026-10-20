from django.contrib import admin

from apps.privacy.models import (
    ConsentRecord,
    DataSubjectRequest,
    PersonalDataIncident,
    PrivacyNotice,
    ProcessingPurpose,
)


@admin.register(ProcessingPurpose)
class ProcessingPurposeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "lawful_basis", "retention_days", "active")
    list_filter = ("lawful_basis", "active")
    search_fields = ("code", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PrivacyNotice)
class PrivacyNoticeAdmin(admin.ModelAdmin):
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
class DataSubjectRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "requester", "request_type", "status", "target_due_at", "created_at")
    list_filter = ("request_type", "status", "target_due_at")
    search_fields = ("id", "requester__email")
    readonly_fields = ("id", "requester", "request_type", "details", "created_at", "updated_at")


@admin.register(PersonalDataIncident)
class PersonalDataIncidentAdmin(admin.ModelAdmin):
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
