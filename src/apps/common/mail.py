"""Sending mail without letting a mail outage break the request that triggered it."""

from __future__ import annotations

import structlog
from django.conf import settings
from django.core.mail import send_mail

logger = structlog.get_logger("apps.common.mail")


def send_safely(subject: str, body: str, to: list[str]) -> bool:
    """Send, log (without addresses) and swallow failures. Returns whether it was handed off.

    ``fail_silently`` is deprecated in Django 6.1 and hides the reason; this keeps the
    behaviour that matters (a notification must not turn into a 500) and records the error.
    """
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, to)
    except Exception:
        logger.exception("mail_failed", subject=subject, recipients=len(to))
        return False
    return True
