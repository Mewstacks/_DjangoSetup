from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from apps.common.admin import AuditedAdminMixin
from apps.webhooks.models import WebhookDelivery, WebhookEndpoint


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("url", "organization", "is_active", "failure_streak")
    list_filter = ("is_active",)
    exclude = ("secret", "previous_secret")
    readonly_fields = ("failure_streak", "disabled_reason", "created_by")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False  # created through the API so the secret is shown once to its owner


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "endpoint", "status", "attempts", "last_status_code")
    list_filter = ("status",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False
