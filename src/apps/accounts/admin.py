from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse

from apps.accounts.models import User
from apps.common.admin import AuditedAdminMixin, SuperuserOnlyFieldsMixin


@admin.register(User)
class UserAdmin(AuditedAdminMixin, SuperuserOnlyFieldsMixin, DjangoUserAdmin):
    # Without this a staff user with change_user could make themselves a superuser. The e-mail
    # is on the list too: changing a superuser's address and then using "forgot password" is an
    # account takeover that needs no privilege other than change_user.
    superuser_only_fields = ("is_staff", "is_superuser", "groups", "user_permissions", "email")
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

    def get_queryset(self, request: HttpRequest) -> QuerySet[User]:
        """Superusers are invisible to everyone else, so there is nothing to edit or reset."""
        queryset = super().get_queryset(request)
        return queryset if request.user.is_superuser else queryset.filter(is_superuser=False)

    def has_change_permission(self, request: HttpRequest, obj: User | None = None) -> bool:
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request: HttpRequest, obj: User | None = None) -> bool:
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    def user_change_password(
        self, request: HttpRequest, id: str, form_url: str = ""
    ) -> HttpResponse:
        """Setting somebody's password from the admin is a superuser act; people use reset."""
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().user_change_password(request, id, form_url)
