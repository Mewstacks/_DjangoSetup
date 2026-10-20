from django.contrib import admin
from django.http import HttpRequest

from apps.common.admin import AuditedAdminMixin, SuperuserOnlyFieldsMixin
from apps.organizations.models import Membership, Organization


class MembershipInline(SuperuserOnlyFieldsMixin, admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user",)
    # The inline is a second door to the same table: it needs the same locks as MembershipAdmin.
    superuser_only_fields = ("role", "user")

    def has_add_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return bool(request.user.is_superuser)


@admin.register(Organization)
class OrganizationAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    readonly_fields = ("created_at", "updated_at")
    inlines = (MembershipInline,)


@admin.register(Membership)
class MembershipAdmin(AuditedAdminMixin, SuperuserOnlyFieldsMixin, admin.ModelAdmin):
    # Granting a role (owner included) on any tenant is a privilege escalation path.
    superuser_only_fields = ("role", "user", "organization")

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Adding a membership grants access to a tenant's data; only a superuser decides that.
        return bool(request.user.is_superuser)

    list_display = ("organization", "user", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("organization__name", "user__email")
    autocomplete_fields = ("organization", "user")
    readonly_fields = ("created_at", "updated_at")
