"""Managing webhook endpoints and watching deliveries (organization owners and admins)."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.request import Request
from rest_framework.response import Response

from apps.audit.services import record_event
from apps.organizations import quotas
from apps.organizations.models import Membership
from apps.organizations.viewsets import OrganizationScopedViewSet
from apps.webhooks import services
from apps.webhooks.events import EVENT_TYPES
from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEvent, new_secret

ADMINS = frozenset({Membership.Role.OWNER, Membership.Role.ADMIN})


class EndpointSerializer(serializers.ModelSerializer[WebhookEndpoint]):
    """Never carries the secret: it is returned once, by create and rotate, and nowhere else."""

    class Meta:
        model = WebhookEndpoint
        fields = (
            "id", "url", "description", "events", "is_active",
            "failure_streak", "disabled_reason", "created_at",
        )  # fmt: skip
        read_only_fields = ("id", "failure_streak", "disabled_reason", "created_at")

    def validate_url(self, value: str) -> str:
        services.validate_endpoint_url(value)
        return value

    def validate_events(self, value: list[str]) -> list[str]:
        unknown = [e for e in value if e != "*" and e not in EVENT_TYPES]
        if unknown or not value:
            raise serializers.ValidationError(
                f"Choose from {sorted(EVENT_TYPES)} or '*'"
                + (f"; unknown: {unknown}" if unknown else "")
            )
        return value


class EndpointViewSet(OrganizationScopedViewSet[WebhookEndpoint]):
    """Endpoints that receive this organization's events."""

    queryset = WebhookEndpoint.objects.all()
    serializer_class = EndpointSerializer
    required_scopes = {"read": "webhooks:read", "write": "webhooks:write"}
    write_roles = ADMINS
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer: serializers.BaseSerializer[WebhookEndpoint]) -> None:
        secret = new_secret()
        organization = self.get_organization()
        quotas.webhook_endpoints(organization)
        serializer.save(organization=organization, secret=secret, created_by=self.request.user)
        self._revealed_secret = secret  # shown once, in the creation response only
        record_event(
            action="webhook.endpoint_created",
            actor=self.request.user,
            organization=organization,
            target=serializer.instance,
            request=self.request._request,
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        response = super().create(request, *args, **kwargs)
        response.data["secret"] = self._revealed_secret
        response["Cache-Control"] = "no-store"
        return response

    @extend_schema(request=None, responses={200: EndpointSerializer})
    @action(detail=True, methods=["post"], url_path="rotate-secret")
    def rotate_secret(self, request: Request, pk: str | None = None) -> Response:
        endpoint = self.get_object()
        fresh = endpoint.rotate()
        record_event(
            action="webhook.secret_rotated",
            actor=request.user,
            organization=endpoint.organization,
            target=endpoint,
            request=request._request,
        )
        body = EndpointSerializer(endpoint).data
        body["secret"] = fresh
        response = Response(body)
        response["Cache-Control"] = "no-store"
        return response

    @extend_schema(request=None, responses={202: None})
    @action(detail=True, methods=["post"])
    def test(self, request: Request, pk: str | None = None) -> Response:
        endpoint = self.get_object()
        organization = endpoint.organization
        with transaction.atomic():
            event = WebhookEvent.objects.create(
                organization=organization, event_type="webhook.test", payload_json="{}"
            )
            delivery = WebhookDelivery.objects.create(
                organization=organization, event=event, endpoint=endpoint
            )
        services.kick([delivery.pk])
        return Response({"delivery_id": str(delivery.pk)}, status=status.HTTP_202_ACCEPTED)


class DeliverySerializer(serializers.ModelSerializer[WebhookDelivery]):
    event_type = serializers.CharField(source="event.event_type", read_only=True)

    class Meta:
        model = WebhookDelivery
        fields = (
            "id", "endpoint", "event_type", "status", "attempts", "next_attempt_at",
            "last_status_code", "last_error", "delivered_at", "created_at",
        )  # fmt: skip
        read_only_fields = fields


class DeliveryViewSet(OrganizationScopedViewSet[WebhookDelivery]):
    """Read-only history, plus redelivery."""

    queryset = WebhookDelivery.objects.select_related("event").all()
    serializer_class = DeliverySerializer
    required_scopes = {"read": "webhooks:read", "write": "webhooks:write"}
    write_roles = ADMINS
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        raise MethodNotAllowed("POST")

    @extend_schema(request=None, responses={202: None})
    @action(detail=True, methods=["post"])
    def redeliver(self, request: Request, pk: str | None = None) -> Response:
        delivery = self.get_object()
        services.redeliver(delivery)
        return Response(status=status.HTTP_202_ACCEPTED)


__all__ = ["DeliveryViewSet", "EndpointViewSet"]
