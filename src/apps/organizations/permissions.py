from __future__ import annotations

from typing import cast

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.organizations.models import Membership


class HasOrganizationContext(BasePermission):
    message = "Select an organization with X-Organization-ID."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return getattr(request, "organization_membership", None) is not None


class IsOrganizationAdministrator(HasOrganizationContext):
    message = "Organization owner or administrator access is required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not super().has_permission(request, view):
            return False
        membership = cast(
            Membership,
            request.organization_membership,  # type: ignore[attr-defined]
        )
        return membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN}
