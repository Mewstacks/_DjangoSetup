"""Where allauth meets this project: signup switch, trusted client IP, encrypted MFA secrets."""

from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.common import encryption
from apps.common.network import client_ip_bucket

MFA_AAD = b"allauth.mfa"


class AccountAdapter(DefaultAccountAdapter):  # type: ignore[misc]
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        """Closed by default: a template deployment opts in with ``SIGNUP_ENABLED=true``."""
        return bool(settings.SIGNUP_ENABLED)

    def get_client_ip(self, request: HttpRequest) -> str:
        # allauth reads X-Forwarded-For itself unless told otherwise; the project resolves the
        # client through the trusted-proxy rules (and an IPv6 /64 bucket) instead.
        ip = client_ip_bucket(request)
        if not ip:
            raise PermissionDenied("Unable to determine client IP address")
        return ip


class MFAAdapter(DefaultMFAAdapter):  # type: ignore[misc]
    """TOTP seeds and recovery codes are stored encrypted, not in the clear."""

    def encrypt(self, text: str) -> str:
        return encryption.encrypt_text(text, associated_data=MFA_AAD)

    def decrypt(self, encrypted_text: str) -> str:
        # An unprefixed value is refused (FIELD_ENCRYPTION_ALLOW_PLAINTEXT is the only way to
        # read one): anyone able to write the row could otherwise plant a seed of their choice.
        return encryption.decrypt_text(encrypted_text, associated_data=MFA_AAD)
