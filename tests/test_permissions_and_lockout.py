from __future__ import annotations

from datetime import timedelta
from typing import cast

from django.test import RequestFactory, override_settings
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.security import axes_lockout_response
from apps.organizations.models import Membership
from apps.organizations.permissions import (
    HasOrganizationContext,
    IsOrganizationAdministrator,
)


@override_settings(AXES_COOLOFF_TIME=timedelta(minutes=30))
def test_lockout_response_is_generic_and_includes_retry_after() -> None:
    request = RequestFactory().post("/api/v1/auth/login/")
    response = axes_lockout_response(request, object(), {"email": "person@example.com"})
    assert response.status_code == 429
    assert response["Retry-After"] == "1800"
    assert b"person@example.com" not in response.content


def test_organization_permissions_require_context_and_admin_role() -> None:
    request = cast(Request, RequestFactory().get("/"))
    view = APIView()
    assert HasOrganizationContext().has_permission(request, view) is False
    assert IsOrganizationAdministrator().has_permission(request, view) is False

    membership = Membership(role=Membership.Role.MEMBER)
    request.organization_membership = membership  # type: ignore[attr-defined]
    assert HasOrganizationContext().has_permission(request, view) is True
    assert IsOrganizationAdministrator().has_permission(request, view) is False

    membership.role = Membership.Role.ADMIN
    assert IsOrganizationAdministrator().has_permission(request, view) is True
