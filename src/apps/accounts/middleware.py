"""Staff must have a second factor before they reach the admin."""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import reverse

from apps.common.exceptions import error_body


def has_mfa(user: object) -> bool:
    from allauth.mfa.utils import is_mfa_enabled

    return bool(is_mfa_enabled(user))


class StaffMFARequiredMiddleware:
    """Refuse ``/admin/`` to a staff account that has no authenticator.

    The admin is the widest door in the system: it can edit memberships, webhook endpoints and
    legal holds. A password alone is not enough for it. The refusal names the page where the
    second factor is set up, so the operator is one click away from fixing it.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if (
            settings.STAFF_MFA_REQUIRED
            and settings.ADMIN_ENABLED
            and (request.path == "/admin" or request.path.startswith("/admin/"))
            and user is not None
            and user.is_authenticated
            and user.is_staff
            and not has_mfa(user)
        ):
            setup = reverse("mfa_index")
            body = error_body(
                403, "mfa_required", f"Two-factor authentication is required for staff: {setup}"
            )
            return JsonResponse(body, status=403)
        return self.get_response(request)
