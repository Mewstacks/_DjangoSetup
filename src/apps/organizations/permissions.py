from __future__ import annotations

from typing import cast

from rest_framework.permissions import SAFE_METHODS, BasePermission
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


class RoleCanWrite(BasePermission):
    """Reads: any active member. Writes: roles in ``view.write_roles`` (default owner/admin/member).

    The tenant filter keeps rows apart; this keeps roles apart. Without it an auditor or a
    billing contact could create, change and delete everything a plain member can.
    """

    message = "Your role is read-only here."
    default_write_roles = frozenset(
        {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.MEMBER}
    )

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method in SAFE_METHODS:
            return True
        membership = getattr(request, "organization_membership", None)
        if membership is None:
            return False
        allowed = getattr(view, "write_roles", self.default_write_roles)
        return membership.role in allowed
