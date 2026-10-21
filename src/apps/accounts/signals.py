"""A reset of the password or of the second factor means the account may have been taken.

API keys authenticate as their owner without a password or a second factor, so a reset that
left them alive would leave the attacker's access in place. Revoking them is cheap (the owner
issues new ones) and the audit trail records it.
"""

from __future__ import annotations

from typing import Any

from allauth.account.signals import password_reset
from allauth.mfa.signals import authenticator_removed, authenticator_reset
from django.conf import settings
from django.dispatch import receiver


def revoke_keys(user: Any, *, reason: str) -> int:
    from apps.apikeys.models import ApiKey
    from apps.audit.services import record_event

    if not settings.APIKEY_REVOKE_ON_CREDENTIAL_RESET:
        return 0
    revoked = 0
    for key in ApiKey.objects.filter(user=user, revoked_at__isnull=True):
        key.revoke()
        revoked += 1
    if revoked:
        record_event(
            action="apikey.revoked_on_reset",
            actor=user,
            metadata={"reason": reason, "count": revoked},
        )
    return revoked


@receiver(password_reset)
def on_password_reset(sender: Any, request: Any, user: Any, **kwargs: Any) -> None:
    revoke_keys(user, reason="password_reset")


@receiver(authenticator_removed)
@receiver(authenticator_reset)
def on_authenticator_change(sender: Any, user: Any, **kwargs: Any) -> None:
    revoke_keys(user, reason="mfa_changed")
