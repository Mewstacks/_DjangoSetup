from __future__ import annotations

import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.common.context import organization_id_var
from apps.organizations.models import Membership


def _error(status: int, code: str, detail: str) -> JsonResponse:
    return JsonResponse(
        {"error": {"status": status, "code": code, "detail": detail}},
        status=status,
    )


class OrganizationContextMiddleware:
    """Resolve an explicit organization header through the authenticated membership.

    There is intentionally no "first organization" fallback: requiring an explicit
    selection prevents accidental cross-tenant access in product endpoints.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.organization = None  # type: ignore[attr-defined]
        request.organization_membership = None  # type: ignore[attr-defined]
        raw_id = request.headers.get("X-Organization-ID")
        if not raw_id:
            return self.get_response(request)
        try:
            organization_id = uuid.UUID(raw_id)
        except ValueError:
            return _error(400, "invalid_organization", "X-Organization-ID must be a UUID.")
        if not request.user.is_authenticated:
            return _error(401, "authentication_required", "Authentication is required.")

        membership = (
            Membership.objects.select_related("organization")
            .filter(
                organization_id=organization_id,
                organization__is_active=True,
                user=request.user,
                is_active=True,
            )
            .first()
        )
        if membership is None:
            return _error(404, "organization_not_found", "Organization was not found.")

        request.organization = membership.organization  # type: ignore[attr-defined]
        request.organization_membership = membership  # type: ignore[attr-defined]
        token = organization_id_var.set(str(organization_id))
        try:
            return self.get_response(request)
        finally:
            organization_id_var.reset(token)
