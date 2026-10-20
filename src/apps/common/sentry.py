from __future__ import annotations

import os
from typing import Any, cast

from apps.common.logging import redact

SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
    "x-csrftoken",
}
SENSITIVE_KEY_FRAGMENTS = {
    "address",
    "authorization",
    "birth",
    "cnpj",
    "cookie",
    "cpf",
    "document",
    "email",
    "name",
    "password",
    "phone",
    "secret",
    "token",
}


def _scrub(value: Any, *, key: str = "") -> Any:
    normalized_key = key.casefold().replace("-", "_")
    if any(fragment in normalized_key for fragment in SENSITIVE_KEY_FRAGMENTS):
        return "[Filtered]"
    if isinstance(value, dict):
        return {child_key: _scrub(child, key=str(child_key)) for child_key, child in value.items()}
    if isinstance(value, list):
        return [_scrub(child) for child in value]
    if isinstance(value, tuple):
        return tuple(_scrub(child) for child in value)
    if isinstance(value, str):
        return redact(value)
    return value


def _sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    event.pop("user", None)
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("cookies", None)
        request.pop("data", None)
        request.pop("query_string", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                key: "[Filtered]" if key.casefold() in SENSITIVE_HEADERS else value
                for key, value in headers.items()
            }
    return cast(dict[str, Any], _scrub(event))


def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    return _sanitize_event(event)


def before_send_transaction(
    event: dict[str, Any],
    hint: dict[str, Any],
) -> dict[str, Any] | None:
    return _sanitize_event(event)


def traces_sampler(sampling_context: dict[str, Any]) -> float:
    transaction_context = sampling_context.get("transaction_context") or {}
    name = str(transaction_context.get("name", ""))
    if "/health/" in name:
        return 0.0
    try:
        return min(max(float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")), 0.0), 1.0)
    except ValueError:
        return 0.0
