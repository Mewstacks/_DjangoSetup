from __future__ import annotations

from django.contrib import admin

from apps.common.admin import AuditedAdminMixin
from apps.flags.models import Flag, FlagRule, Setting


class RuleInline(admin.TabularInline):
    model = FlagRule
    extra = 0
    autocomplete_fields = ("user", "organization")


@admin.register(Flag)
class FlagAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("key", "default_enabled", "description")
    search_fields = ("key",)
    inlines = (RuleInline,)


@admin.register(Setting)
class SettingAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("key", "organization", "value_json")
    search_fields = ("key",)
