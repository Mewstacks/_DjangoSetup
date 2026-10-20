"""Notes as a classic REST resource, next to the same operations exposed as actions."""

from __future__ import annotations

from typing import Any, cast

from rest_framework import serializers
from rest_framework.request import Request

from apps.actions.rest import context_from_request
from apps.examples import services
from apps.examples.models import Note
from apps.organizations.viewsets import OrganizationScopedViewSet


class NoteSerializer(serializers.ModelSerializer[Note]):
    class Meta:
        model = Note
        fields = ("id", "title", "body", "archived_at", "created_at", "updated_at")
        read_only_fields = ("id", "archived_at", "created_at", "updated_at")


class NoteViewSet(OrganizationScopedViewSet[Note]):
    queryset = Note.objects.all().order_by("-created_at")
    serializer_class = NoteSerializer
    required_scopes = {"read": "notes:read", "write": "notes:write"}
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer: serializers.BaseSerializer[Note]) -> None:
        ctx = context_from_request(self._ctx_request())
        data: dict[str, Any] = serializer.validated_data
        serializer.instance = services.create_note(
            ctx, title=data["title"], body=data.get("body", "")
        )

    def perform_update(self, serializer: serializers.BaseSerializer[Note]) -> None:
        ctx = context_from_request(self._ctx_request())
        data: dict[str, Any] = serializer.validated_data
        serializer.instance = services.update_note(
            ctx, cast(Note, serializer.instance), title=data.get("title"), body=data.get("body")
        )

    def perform_destroy(self, instance: Note) -> None:
        # Notes are archived, not deleted: the audit trail keeps pointing at a real row.
        services.archive_note(context_from_request(self._ctx_request()), instance)

    def _ctx_request(self) -> Request:
        return self.request
