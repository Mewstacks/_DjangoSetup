from __future__ import annotations

import contextlib

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.exceptions import ImproperlyConfigured
from django.dispatch import receiver

from apps.audit.services import record_event
from apps.common.encryption import blind_index


@receiver(user_logged_in)
def audit_login(sender: object, request: object, user: object, **kwargs: object) -> None:
    record_event(action="auth.login", actor=user, request=request)


@receiver(user_logged_out)
def audit_logout(sender: object, request: object, user: object, **kwargs: object) -> None:
    record_event(action="auth.logout", actor=user, request=request)


@receiver(user_login_failed)
def audit_login_failure(
    sender: object,
    credentials: dict[str, object],
    request: object,
    **kwargs: object,
) -> None:
    # Record a non-reversible index of the attempted account, so a targeted brute-force
    # against one login is visible in the trail — without ever storing the email itself.
    # Failing to compute the index must never break authentication, so it degrades to no
    # index when the HMAC key is absent (development) or unusable.
    metadata: dict[str, object] = {}
    username = ""
    if credentials:
        raw = credentials.get("username") or credentials.get("email")
        username = str(raw).strip() if raw else ""
    if username and settings.PRIVACY_HMAC_KEY:
        with contextlib.suppress(ImproperlyConfigured):
            metadata["username_index"] = blind_index(username, namespace="audit-login-username")
    record_event(action="auth.login_failed", request=request, success=False, metadata=metadata)
