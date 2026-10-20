"""Structured logging with redaction.

Every record - Django's, gunicorn's, Temporal's, a third-party library's or our own
``structlog`` calls - ends up as one JSON line produced by one pipeline:

    record -> add context (request/org/actor/channel/workflow) -> render exception ->
    redact -> JSON

Redaction is the last step before rendering, so nothing a processor or a library adds can
bypass it. It is deliberately aggressive: a false positive costs a readable log line, a false
negative is a personal-data leak (LGPD art. 46).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

import structlog
from structlog.typing import EventDict, Processor

from apps.common.context import LOG_CONTEXT_VARS

REDACTED = "[REDACTED]"

_SENSITIVE_NAMES = (
    r"password|passwd|pwd|secret[\w-]*|token|authorization|cookie|api[_-]?key|sessionid|"
    r"csrftoken|access[_-]?token|refresh[_-]?token|client[_-]?secret|private[_-]?key|"
    r"aws_secret_access_key|signature"
)

# Order matters: longer / more specific shapes first so a CNPJ is not half-eaten as a CPF.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*"), "[REDACTED_JWT]"),
    (re.compile(r"\b[a-z]{2,8}_[0-9a-f]{16}_[0-9a-f]{64}\b"), "[REDACTED_KEY]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+@"), "[REDACTED]@"),
    (
        # key=value, key: value, "key": "value", 'key': 'value' (quotes optional)
        re.compile(
            rf"""(?ix)(["']?\b(?:{_SENSITIVE_NAMES})["']?\s*[=:]\s*)(?:"[^"]*"|'[^']*'|[^\s,;&}}\]]+)"""
        ),
        r"\1" + REDACTED,
    ),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "[REDACTED_EMAIL]"),
    (re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[REDACTED_CNPJ]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[REDACTED_CPF]"),
    (
        re.compile(r"(?<![\w.])(?:\+?55[\s-]?)?\(?\d{2}\)?[\s-]?9?\d{4}[\s-]?\d{4}(?![\w.])"),
        "[REDACTED_PHONE]",
    ),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[REDACTED_IP]"),
    (re.compile(r"\b(?:[0-9a-f]{1,4}:){3,7}[0-9a-f]{0,4}\b", re.IGNORECASE), "[REDACTED_IP]"),
)

_SENSITIVE_KEY = re.compile(
    r"(?i)(password|passwd|secret|token|authorization|cookie|api[_-]?key|sessionid|csrf|"
    r"private[_-]?key|signature|cpf|cnpj|email|phone|birth|address|full_name|document)"
)

# Keys the pipeline itself fills with identifiers and timestamps. Their values are never
# user text, and pattern-matching a UUID or an ISO timestamp can mangle it by accident.
_SAFE_KEYS = {
    "timestamp",
    "level",
    "logger",
    "request_id",
    "organization_id",
    "actor_id",
    "workflow_id",
    "activity",
    "channel",
    "trace_id",
    "span_id",
}


def redact(value: str) -> str:
    for pattern, replacement in _PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def redact_value(value: Any, *, key: str = "") -> Any:
    """Redact a structured value: by key name first, then by content."""
    if key in _SAFE_KEYS:
        return value
    if key and _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_value(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [redact_value(v) for v in value]
    return value


# --- structlog processors -------------------------------------------------------------


def add_app_context(logger: Any, method: str, event_dict: EventDict) -> EventDict:
    for name, var in LOG_CONTEXT_VARS.items():
        current = var.get()
        if current is not None and name not in event_dict:
            event_dict[name] = current
    try:  # trace correlation when OpenTelemetry is active; absent otherwise
        from opentelemetry import trace  # type: ignore[import-not-found,unused-ignore]

        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            event_dict.setdefault("trace_id", format(span_context.trace_id, "032x"))
            event_dict.setdefault("span_id", format(span_context.span_id, "016x"))
    except ImportError:
        pass
    return event_dict


def redact_event(logger: Any, method: str, event_dict: EventDict) -> EventDict:
    return {key: redact_value(value, key=key) for key, value in event_dict.items()}


def _context_processors() -> list[Processor]:
    """Run for native structlog events and (as ``foreign_pre_chain``) for stdlib records."""
    return [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        add_app_context,
        structlog.processors.StackInfoRenderer(),
    ]


def build_formatter() -> logging.Formatter:
    """``LOGGING['formatters'][...]['()']`` target: JSON for stdlib and structlog records alike.

    Exception rendering and redaction sit in the formatter's own ``processors`` - the one chain
    both kinds of record pass through last - so no logging path can skip them.
    """
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_context_processors(),
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            redact_event,
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(ensure_ascii=False, default=str),
        ],
    )


def configure_structlog() -> None:
    """Route ``structlog.get_logger()`` through the stdlib handlers configured in LOGGING."""
    structlog.configure(
        processors=[
            *_context_processors(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


# --- access logs ----------------------------------------------------------------------


class AccessLogScrubFilter(logging.Filter):
    """Rewrite uvicorn/gunicorn access records: no query string, no client address.

    Query strings routinely carry tokens and personal identifiers, and the peer address is
    personal data; the audit trail keeps an HMAC of the validated client IP instead.
    uvicorn's worker replaces the handlers on these loggers with gunicorn's, so the filter
    (which stays on the logger) emits the final JSON line itself.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:  # uvicorn: addr, method, path, ver, code
            _, method, full_path, _version, status = args[:5]
            path = str(full_path).split("?", 1)[0]
            message = f"{method} {path} {status}"
        else:
            message = redact(str(record.getMessage())).split("?", 1)[0]
        record.msg = json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": "INFO",
                "logger": record.name,
                "message": redact(message),
            }
        )
        record.args = ()
        return True
