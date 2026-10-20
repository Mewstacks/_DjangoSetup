from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from apps.common.context import organization_id_var, request_id_var

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
SECRET_PATTERN = re.compile(
    r"(?i)(password|passwd|secret|token|authorization|cookie)(\s*[=:]\s*)([^\s,;]+)"
)


def redact(value: str) -> str:
    value = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    value = BEARER_PATTERN.sub("Bearer [REDACTED]", value)
    return SECRET_PATTERN.sub(r"\1\2[REDACTED]", value)


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Render before redacting so numeric values keep their type for %-style
        # format strings. Clearing args then prevents another interpolation pass.
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.organization_id = organization_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "organization_id": getattr(record, "organization_id", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)
