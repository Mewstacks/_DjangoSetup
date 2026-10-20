from __future__ import annotations

from typing import Any

from django.core.exceptions import SuspiciousOperation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.common.context import request_id_var


def error_body(status: int, code: str, detail: Any) -> dict[str, Any]:
    """The one error envelope every surface uses (REST, middleware, lockout, MCP)."""
    return {
        "error": {
            "status": status,
            "code": code,
            "detail": detail,
            "request_id": request_id_var.get(),
        }
    }


class DomainError(Exception):
    """An error the application raises on purpose, with text written for the caller.

    Raised by services and actions on every channel; the REST handler, the MCP wrapper and the
    CLI each map it to their own wire format. Anything that is *not* a DomainError is a bug and
    is reported as a generic 500.
    """

    status = 400
    code = "error"

    def __init__(self, detail: str = "", *, code: str | None = None, extra: Any = None) -> None:
        super().__init__(detail or self.code)
        self.detail = detail or self.code
        if code:
            self.code = code
        self.extra = extra

    def payload(self) -> Any:
        return self.extra if self.extra is not None else self.detail


class NotFound(DomainError):
    status = 404
    code = "not_found"


class Forbidden(DomainError):
    status = 403
    code = "forbidden"


class Unauthenticated(DomainError):
    status = 401
    code = "authentication_required"


class Invalid(DomainError):
    status = 422
    code = "invalid"


class Conflict(DomainError):
    status = 409
    code = "conflict"


class TooLarge(DomainError):
    status = 413
    code = "payload_too_large"


class RateLimited(DomainError):
    status = 429
    code = "rate_limited"


class Unavailable(DomainError):
    status = 503
    code = "unavailable"


def _translate(exc: Exception) -> Exception:
    # Model.full_clean() and service code raise Django's ValidationError; without this they
    # surface as a 500. SuspiciousOperation (for example a tampered ciphertext) must read as a
    # client error, never leak its message.
    if isinstance(exc, DjangoValidationError):
        detail: Any = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
        return drf_exceptions.ValidationError(detail)
    if isinstance(exc, RecursionError):
        return drf_exceptions.ParseError("Invalid request.")
    if isinstance(exc, SuspiciousOperation):
        return drf_exceptions.ParseError("Invalid request.")
    return exc


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, DomainError):
        return Response(error_body(exc.status, exc.code, exc.payload()), status=exc.status)
    exc = _translate(exc)
    response = exception_handler(exc, context)
    if response is None:
        return None

    response.data = error_body(
        response.status_code, getattr(exc, "default_code", "error"), response.data
    )
    return response
