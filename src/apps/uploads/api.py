from __future__ import annotations

from typing import Any

from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.audit.services import record_event
from apps.common.exceptions import Invalid
from apps.organizations.viewsets import OrganizationScopedViewSet
from apps.uploads import services
from apps.uploads.models import UploadedFile


class UploadSerializer(serializers.ModelSerializer[UploadedFile]):
    class Meta:
        model = UploadedFile
        fields = ("id", "original_name", "content_type", "size", "sha256", "created_at")
        read_only_fields = fields


class UploadBody(serializers.Serializer[Any]):
    file = serializers.FileField()


class UploadViewSet(OrganizationScopedViewSet[UploadedFile]):
    """Files stored for the organization: validated by content, served as attachments."""

    queryset = UploadedFile.objects.all()
    serializer_class = UploadSerializer
    parser_classes = [MultiPartParser]
    required_scopes = {"read": "uploads:read", "write": "uploads:write"}
    http_method_names = ["get", "post", "delete", "head", "options"]

    @extend_schema(request={"multipart/form-data": UploadBody}, responses={201: UploadSerializer})
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        body = UploadBody(data=request.data)
        body.is_valid(raise_exception=True)
        upload = body.validated_data["file"]
        if upload is None:
            raise Invalid("Send a file.")
        row = services.store(
            upload,
            organization=self.get_organization(),
            user=request.user,
            request=request._request,
        )
        return Response(UploadSerializer(row).data, status=status.HTTP_201_CREATED)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        raise MethodNotAllowed(request.method or "PUT")

    def perform_destroy(self, instance: UploadedFile) -> None:
        services.remove(instance, user=self.request.user, request=self.request._request)

    @extend_schema(request=None, responses={(200, "application/octet-stream"): bytes})
    @action(detail=True, methods=["get"])
    def download(self, request: Request, pk: str | None = None) -> FileResponse:
        row = self.get_object()
        record_event(
            action="upload.downloaded",
            actor=request.user,
            organization=row.organization,
            target=row,
            request=request._request,
        )
        response = FileResponse(
            row.file.open("rb"),
            as_attachment=True,
            filename=row.original_name,
            content_type=row.content_type,
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "sandbox; default-src 'none'"
        response["Cache-Control"] = "private, no-store"
        return response


__all__ = ["UploadViewSet"]
