from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from apps.apikeys.models import ApiKey
from apps.common.admin import AuditedAdminMixin


@admin.register(ApiKey)
class ApiKeyAdmin(AuditedAdminMixin, admin.ModelAdmin):
    """Read-only: keys are minted through the API so the secret is shown once to its owner."""

    list_display = ("label", "organization", "user", "kind", "last_used_at", "revoked_at")
    list_filter = ("kind", "revoked_at")
    search_fields = ("label", "public_id", "user__email")
    readonly_fields = (
        "user",
        "organization",
        "label",
        "kind",
        "public_id",
        "scopes",
        "expires_at",
        "last_used_at",
        "revoked_at",
        "allowed_ips",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
