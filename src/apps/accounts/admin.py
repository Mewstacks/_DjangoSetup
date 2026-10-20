from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import User
from apps.common.admin import AuditedAdminMixin, SuperuserOnlyFieldsMixin


@admin.register(User)
class UserAdmin(AuditedAdminMixin, SuperuserOnlyFieldsMixin, DjangoUserAdmin):
    # Without this a staff user with change_user could make themselves a superuser.
    superuser_only_fields = ("is_staff", "is_superuser", "groups", "user_permissions")
    ordering = ("email",)
    list_display = ("email", "full_name", "is_active", "is_staff", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")
    readonly_fields = ("date_joined", "updated_at", "last_login", "anonymized_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Audit", {"fields": ("last_login", "date_joined", "updated_at", "anonymized_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2", "is_staff"),
            },
        ),
    )
