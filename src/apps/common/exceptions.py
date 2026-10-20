from __future__ import annotations

from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.common.context import request_id_var


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(exc, context)
    if response is None:
        return None

    response.data = {
        "error": {
            "status": response.status_code,
            "code": getattr(exc, "default_code", "error"),
            "detail": response.data,
            "request_id": request_id_var.get(),
        }
    }
    return response
