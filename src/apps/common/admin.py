from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest

admin.site.site_header = "SaaS Operations"
admin.site.site_title = "SaaS Operations"
admin.site.index_title = "Restricted operations console"


class AuditedAdminMixin:
    """Every create, change and delete made in the admin leaves an audit event.

    Django's own ``LogEntry`` is mutable and deletable; the audit trail is not. Only field
    *names* are recorded, never values, so the event cannot carry personal data.
    """

    def _audit(
        self, request: HttpRequest, action: str, obj: Model, fields: list[str] | None = None
    ) -> None:
        from apps.audit.services import record_event

        record_event(
            action=f"admin.{obj._meta.label_lower}.{action}",
            actor=request.user,
            target=obj,
            request=request,
            metadata={"fields": sorted(fields)} if fields else {},
        )

    def save_model(self, request: HttpRequest, obj: Model, form: Any, change: bool) -> None:
        super().save_model(request, obj, form, change)  # type: ignore[misc]
        self._audit(request, "change" if change else "create", obj, list(form.changed_data))

    def delete_model(self, request: HttpRequest, obj: Model) -> None:
        self._audit(request, "delete", obj)
        super().delete_model(request, obj)  # type: ignore[misc]


class SuperuserOnlyFieldsMixin:
    """Fields that grant privilege are read-only unless the editor is a superuser."""

    superuser_only_fields: tuple[str, ...] = ()

    def get_readonly_fields(self, request: HttpRequest, obj: Model | None = None) -> Any:
        fields = list(super().get_readonly_fields(request, obj))  # type: ignore[misc]
        if not request.user.is_superuser:
            fields.extend(f for f in self.superuser_only_fields if f not in fields)
        return fields
