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
    exc = _translate(exc)
    response = exception_handler(exc, context)
    if response is None:
        return None

    response.data = error_body(
        response.status_code, getattr(exc, "default_code", "error"), response.data
    )
    return response
