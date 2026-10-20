from __future__ import annotations

from typing import TypeVar, cast

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import BaseSerializer

from apps.organizations.models import Organization, OrganizationScopedModel
from apps.organizations.permissions import HasOrganizationContext

ScopedModelT = TypeVar("ScopedModelT", bound=OrganizationScopedModel)


class OrganizationScopedViewSet(viewsets.ModelViewSet[ScopedModelT]):
    """Base class for every resource that belongs to a single organization.

    Subclasses set ``queryset`` and ``serializer_class`` and nothing else. The tenant
    filter lives here so that forgetting it is impossible instead of catastrophic, and
    ``organization`` is assigned from the request rather than accepted from the payload.
    """

    permission_classes = [IsAuthenticated, HasOrganizationContext]
    lookup_value_converter = "uuid"

    def get_organization(self) -> Organization:
        # HasOrganizationContext already rejected the request if this is unset.
        return cast(Organization, self.request.organization)  # type: ignore[attr-defined]

    def get_queryset(self) -> QuerySet[ScopedModelT]:
        queryset = cast(QuerySet[ScopedModelT], self.queryset)
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        return queryset.filter(organization=self.get_organization())

    def perform_create(self, serializer: BaseSerializer[ScopedModelT]) -> None:
        serializer.save(organization=self.get_organization())

    def perform_update(self, serializer: BaseSerializer[ScopedModelT]) -> None:
        # Pin the tenant on write as well as create: even if a subclass serializer exposes
        # ``organization`` as writable, a PATCH/PUT can never move a row to another tenant.
        serializer.save(organization=self.get_organization())
