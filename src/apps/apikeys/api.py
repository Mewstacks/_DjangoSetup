"""Managing API keys: session-only, so a leaked key can never mint more keys."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from django.db.models import QuerySet
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import User
from apps.actions.registry import known_scopes, read_scopes
from apps.apikeys.models import ApiKey
from apps.audit.services import record_event
from apps.common.exceptions import Forbidden
from apps.organizations.models import Membership, Organization
from apps.organizations.permissions import HasOrganizationContext

PROFILES = {"read": "Every read scope", "full": "Every scope your role allows"}
MANAGING_ROLES = {Membership.Role.OWNER, Membership.Role.ADMIN}


def scopes_for_profile(profile: str, role: str) -> list[str]:
    scopes = known_scopes() if profile == "full" else read_scopes()
    if role not in {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.MEMBER}:
        scopes = scopes & read_scopes()  # auditors and billing contacts never get write scopes
    return sorted(scopes)


class ApiKeySerializer(serializers.ModelSerializer[ApiKey]):
    class Meta:
        model = ApiKey
        fields = (
            "id",
            "label",
            "kind",
            "public_id",
            "scopes",
            "expires_at",
            "last_used_at",
            "revoked_at",
            "allowed_ips",
            "created_at",
        )
        read_only_fields = fields


class ApiKeyCreateSerializer(serializers.Serializer[dict[str, Any]]):
    label = serializers.CharField(max_length=120)  # type: ignore[assignment]
    kind = serializers.ChoiceField(choices=ApiKey.Kind.choices, default=ApiKey.Kind.API)
    profile = serializers.ChoiceField(choices=list(PROFILES), required=False)
    scopes = serializers.ListField(child=serializers.CharField(), required=False)
    expires_in_days = serializers.IntegerField(min_value=1, max_value=365, required=False)
    allowed_ips = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if bool(attrs.get("profile")) == bool(attrs.get("scopes")):
            raise serializers.ValidationError("Send either profile or scopes.")
        return attrs


class ApiKeySecretSerializer(ApiKeySerializer):
    secret = serializers.CharField(read_only=True)

    class Meta(ApiKeySerializer.Meta):
        fields = (*ApiKeySerializer.Meta.fields, "secret")  # type: ignore[assignment]
        read_only_fields = fields  # type: ignore[assignment]


class ApiKeyViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet[ApiKey],
):
    """Create, list, rotate and revoke keys of the selected organization."""

    serializer_class = ApiKeySerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, HasOrganizationContext]
    queryset = ApiKey.objects.none()
    lookup_value_converter = "uuid"

    def _membership(self) -> Membership:
        return cast(Membership, self.request.organization_membership)  # type: ignore[attr-defined]

    def get_queryset(self) -> QuerySet[ApiKey]:
        if getattr(self, "swagger_fake_view", False):
            return ApiKey.objects.none()
        organization = cast(Organization, self.request.organization)  # type: ignore[attr-defined]
        queryset = ApiKey.objects.filter(organization=organization)
        if self._membership().role not in MANAGING_ROLES:
            queryset = queryset.filter(user=cast(User, self.request.user))  # members: own keys
        return queryset

    @extend_schema(request=ApiKeyCreateSerializer, responses={201: ApiKeySecretSerializer})
    def create(self, request: Request) -> Response:
        membership = self._membership()
        if membership.role not in {*MANAGING_ROLES, Membership.Role.MEMBER}:
            raise Forbidden("Your role cannot create keys.")
        serializer = ApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        allowed = set(scopes_for_profile("full", membership.role))
        scopes = (
            scopes_for_profile(data["profile"], membership.role)
            if data.get("profile")
            else sorted(set(data["scopes"]))
        )
        if not set(scopes) <= allowed:
            # A key can be narrower than its owner's role, never wider.
            raise Forbidden("Some requested scopes exceed your role.", code="scope_exceeds_role")
        expires_at = (
            timezone.now() + timedelta(days=data["expires_in_days"])
            if data.get("expires_in_days")
            else None
        )
        key, raw = ApiKey.issue(
            user=request.user,
            organization=membership.organization,
            label=data["label"],
            scopes=scopes,
            kind=data["kind"],
            expires_at=expires_at,
            allowed_ips=data.get("allowed_ips", []),
        )
        record_event(
            action="apikey.created",
            actor=request.user,
            organization=membership.organization,
            target=key,
            request=request._request,
            metadata={"kind": key.kind, "scope_count": len(scopes)},
        )
        body = ApiKeySecretSerializer(key).data
        body["secret"] = raw
        response = Response(body, status=status.HTTP_201_CREATED)
        response["Cache-Control"] = "no-store"
        return response

    def perform_destroy(self, instance: ApiKey) -> None:
        instance.revoke()
        record_event(
            action="apikey.revoked",
            actor=self.request.user,
            organization=instance.organization,
            target=instance,
            request=self.request._request,
        )

    @extend_schema(request=None, responses={201: ApiKeySecretSerializer})
    @action(detail=True, methods=["post"])
    def rotate(self, request: Request, pk: str | None = None) -> Response:
        old = self.get_object()
        if not old.is_active:
            raise Forbidden("Only an active key can be rotated.")
        fresh, raw = old.rotate()
        record_event(
            action="apikey.rotated",
            actor=request.user,
            organization=fresh.organization,
            target=fresh,
            request=request._request,
        )
        body = ApiKeySecretSerializer(fresh).data
        body["secret"] = raw
        response = Response(body, status=status.HTTP_201_CREATED)
        response["Cache-Control"] = "no-store"
        return response
