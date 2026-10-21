from __future__ import annotations

from django.contrib import admin

from apps.common.admin import AuditedAdminMixin
from apps.uploads.models import UploadedFile


@admin.register(UploadedFile)
class UploadedFileAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("original_name", "organization", "content_type", "size", "scan_status")
    readonly_fields = tuple(f.name for f in UploadedFile._meta.fields)
    search_fields = ("original_name", "sha256")

    def has_add_permission(self, request: object) -> bool:
        return False
