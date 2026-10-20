from django.contrib import admin

from apps.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "action", "actor", "organization", "success", "request_id")
    list_filter = ("success", "action", "occurred_at")
    search_fields = ("request_id", "target_id", "action")
    readonly_fields = (
        "id",
        "occurred_at",
        "actor",
        "organization",
        "action",
        "target_type",
        "target_id",
        "request_id",
        "ip_hash",
        "success",
        "metadata",
    )

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: object, obj: object = None) -> bool:
        return False
