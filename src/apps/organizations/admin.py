from django.contrib import admin

from apps.common.admin import AuditedAdminMixin, SuperuserOnlyFieldsMixin
from apps.organizations.models import Membership, Organization


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user",)


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
    superuser_only_fields = ("role",)
    list_display = ("organization", "user", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("organization__name", "user__email")
    autocomplete_fields = ("organization", "user")
    readonly_fields = ("created_at", "updated_at")
