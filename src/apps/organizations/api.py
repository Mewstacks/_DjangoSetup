from __future__ import annotations

from typing import cast

from django.db import transaction
from django.db.models import OuterRef, QuerySet, Subquery
from rest_framework import serializers, viewsets
from rest_framework.throttling import BaseThrottle

from apps.accounts.models import User
from apps.audit.services import record_event
from apps.common.throttling import IPUserRateThrottle
from apps.organizations.models import Membership, Organization


class OrganizationCreateThrottle(IPUserRateThrottle):
    scope = "organization_create"


class OrganizationSerializer(serializers.ModelSerializer[Organization]):
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ("id", "name", "slug", "is_active", "current_user_role", "created_at")
        read_only_fields = ("id", "is_active", "current_user_role", "created_at")

    def get_current_user_role(self, organization: Organization) -> str | None:
        # Supplied by the annotation in OrganizationViewSet.get_queryset, and set
        # directly on create(); never by walking the membership list, which would load
        # every member of every organization on the page.
        role = getattr(organization, "current_user_role", None)
        return str(role) if role else None

    @transaction.atomic
    def create(self, validated_data: dict[str, object]) -> Organization:
        organization = Organization.objects.create(**validated_data)
        Membership.objects.create(
            organization=organization,
            user=self.context["request"].user,
            role=Membership.Role.OWNER,
        )
        organization.current_user_role = Membership.Role.OWNER  # type: ignore[attr-defined]
        record_event(
            action="organization.created",
            actor=self.context["request"].user,
            organization=organization,
            target=organization,
        )
        return organization


class OrganizationViewSet(viewsets.ModelViewSet[Organization]):
    queryset = Organization.objects.none()
    serializer_class = OrganizationSerializer
    http_method_names = ["get", "post", "head", "options"]
    lookup_value_converter = "uuid"

    def get_queryset(self) -> QuerySet[Organization]:
        if getattr(self, "swagger_fake_view", False):
            return Organization.objects.none()
        user = cast(User, self.request.user)
        active_memberships = Membership.objects.filter(user=user, is_active=True)
        # A subquery instead of a join keeps this O(1) rows per organization: the join
        # form needed distinct() and a prefetch of every membership just to read one role.
        return Organization.objects.filter(
            pk__in=active_memberships.values("organization_id")
        ).annotate(
            current_user_role=Subquery(
                active_memberships.filter(organization=OuterRef("pk")).values("role")[:1]
            )
        )

    def get_throttles(self) -> list[BaseThrottle]:
        if self.action == "create":
            return [OrganizationCreateThrottle()]
        return super().get_throttles()
