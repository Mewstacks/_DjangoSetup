from __future__ import annotations

import time
from typing import Any

from django.conf import settings
from django.http import HttpRequest, JsonResponse

from apps.common.exceptions import error_body


def axes_username(request: HttpRequest | None, credentials: dict[str, Any] | None = None) -> str:
    """Resolve the account being attacked for django-axes.

    Axes reads the username out of the credentials dict under AXES_USERNAME_FORM_FIELD,
    but the ``user_login_failed`` signal carries the raw kwargs that were handed to
    ``django.contrib.auth.authenticate`` -- so the address arrives under "username" while
    the backend call maps it to "email". Without covering both, every failure is recorded
    against username=None and the per-account lockout degrades into a per-IP one.
    """

    sources: list[Any] = [credentials or {}]
    if request is not None:
        sources.append(getattr(request, "data", None) or request.POST)
    for source in sources:
        for key in ("email", "username"):
            value = source.get(key)
            if value:
                return str(value).strip().casefold()
    return ""


def recently_authenticated(request: HttpRequest, *, max_age: int) -> bool:
    """Did this session sign in, or re-enter its password or second factor, within ``max_age`` s.

    allauth records every authentication step in the session. A session that is hours old has
    proved nothing lately, and creating a credential that outlives it should need a fresh proof.
    """
    from allauth.account.authentication import get_authentication_records

    now = time.time()
    records = get_authentication_records(request)
    return any(now - float(record.get("at", 0)) <= max_age for record in records)


def axes_lockout_response(
    request: HttpRequest,
    response: object,
    credentials: dict[str, Any],
    *args: object,
    **kwargs: object,
) -> JsonResponse:
    retry_after = int(settings.AXES_COOLOFF_TIME.total_seconds())
    result = JsonResponse(
        error_body(
            429, "authentication_locked", "Too many authentication attempts. Try again later."
        ),
        status=429,
    )
    result["Retry-After"] = str(retry_after)
    return result
