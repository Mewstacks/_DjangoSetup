from __future__ import annotations

import base64
import hashlib
import hmac
import os
from functools import lru_cache
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation, ValidationError
from django.db import models

LEGACY_PREFIX = "enc:v1"
PREFIX = "enc:v2"
HKDF_INFO = b"saas/field-encryption/v2"


def _decode_key(encoded: str, key_id: str) -> bytes:
    try:
        key = base64.urlsafe_b64decode(encoded)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(f"Field encryption key {key_id!r} is not valid base64.") from exc
    if len(key) != 32:
        raise ImproperlyConfigured(f"Field encryption key {key_id!r} must decode to 32 bytes.")
    return key


@lru_cache(maxsize=32)
def _key(key_id: str) -> bytes:
    encoded = settings.FIELD_ENCRYPTION_KEYS.get(key_id)
    if not encoded:
        raise ImproperlyConfigured(f"Field encryption key {key_id!r} is unavailable.")
    return _decode_key(encoded, key_id)


@lru_cache(maxsize=64)
def derive_key(key_id: str, purpose: bytes) -> bytes:
    """HKDF subkey for one purpose, so a ring key never encrypts two unrelated things.

    Field encryption (v2), the Temporal payload codec and any future use each get their own
    derived key; compromising the use of one does not hand over the others' ciphertext.
    """
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=purpose).derive(_key(key_id))


def clear_key_cache() -> None:
    """Forget decoded keys; tests and key-ring reloads call this after changing settings."""
    _key.cache_clear()
    derive_key.cache_clear()


def _aad(associated_data: bytes) -> bytes:
    # A scheme marker in the AAD means a model rename or a future format change fails closed
    # instead of silently verifying under a different binding.
    return b"v2|" + associated_data


def encrypt_text(value: str, *, associated_data: bytes = b"") -> str:
    """Always encrypt. A value that merely looks like a token is user data like any other."""
    if not value:
        return value
    key_id = settings.FIELD_ENCRYPTION_ACTIVE_KEY_ID
    if not key_id:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_ACTIVE_KEY_ID is not configured.")
    nonce = os.urandom(12)
    ciphertext = AESGCM(derive_key(key_id, HKDF_INFO)).encrypt(
        nonce, value.encode(), _aad(associated_data)
    )
    encoded_nonce = base64.urlsafe_b64encode(nonce).decode()
    encoded_ciphertext = base64.urlsafe_b64encode(ciphertext).decode()
    return f"{PREFIX}:{key_id}:{encoded_nonce}:{encoded_ciphertext}"


def is_ciphertext(value: str) -> bool:
    return value.startswith((f"{PREFIX}:", f"{LEGACY_PREFIX}:"))


def decrypt_text(value: str, *, associated_data: bytes = b"") -> str:
    """Decrypt a stored token.

    ``FIELD_ENCRYPTION_ALLOW_PLAINTEXT`` (default False) controls what an unprefixed value
    means. Off, it is rejected: anyone able to write a row could otherwise inject plaintext
    that reads back as if the application had written it. Switch it on only while migrating
    a column that held plaintext before it became encrypted.
    """
    if not value:
        return value
    if not is_ciphertext(value):
        if getattr(settings, "FIELD_ENCRYPTION_ALLOW_PLAINTEXT", False):
            return value
        raise SuspiciousOperation("Encrypted field authentication failed.")
    try:
        prefix, version, key_id, encoded_nonce, encoded_ciphertext = value.split(":", 4)
        nonce = base64.urlsafe_b64decode(encoded_nonce)
        ciphertext = base64.urlsafe_b64decode(encoded_ciphertext)
        scheme = f"{prefix}:{version}"
        if scheme == PREFIX:
            plaintext = AESGCM(derive_key(key_id, HKDF_INFO)).decrypt(
                nonce, ciphertext, _aad(associated_data)
            )
        elif scheme == LEGACY_PREFIX:
            plaintext = AESGCM(_key(key_id)).decrypt(nonce, ciphertext, associated_data)
        else:
            raise ValueError("unknown scheme")
    except (ValueError, InvalidTag, ImproperlyConfigured) as exc:
        # ImproperlyConfigured: the stored token names a key id that is not in the ring.
        # That is a property of the (attacker- or corruption-supplied) *data*, not of the
        # process config, so it must surface as a handled 400, never an unhandled 500 that
        # would break every subsequent read of the owner's row and the admin changelist.
        raise SuspiciousOperation("Encrypted field authentication failed.") from exc
    return plaintext.decode()


def blind_index(value: str, *, namespace: str) -> str:
    secret = settings.PRIVACY_HMAC_KEY
    if not secret:
        raise ImproperlyConfigured("PRIVACY_HMAC_KEY is not configured.")
    normalized = value.strip().casefold().encode()
    message = namespace.encode() + b"\0" + normalized
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def validate_not_ciphertext(value: str) -> None:
    """Refuse user input shaped like our own token.

    Encryption no longer depends on this (everything is encrypted), but a value that starts
    with the marker is never legitimate input and would confuse operators reading the column.
    """
    if value and is_ciphertext(value):
        raise ValidationError("Value must not begin with the internal encryption marker.")


class EncryptedTextField(models.TextField):  # type: ignore[type-arg]
    description = "AES-256-GCM encrypted text"
    default_validators = [validate_not_ciphertext]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("editable", True)
        super().__init__(*args, **kwargs)

    def associated_data(self) -> bytes:
        """Bind each ciphertext to the column it belongs to.

        Without this, GCM authenticates the bytes but not their location, so anyone with
        write access to the database can move a ciphertext from one model or column into
        another and it still decrypts cleanly. Row identity is deliberately not part of
        the binding: Django hydrates a field before the instance exists, so a same-column
        row swap by someone with database write access remains possible. The mitigation is
        operational (separate DB roles, the audit trail); see the security docs.
        """

        model = getattr(self, "model", None)
        if model is None:
            return b""
        return f"{model._meta.label_lower}:{self.attname}".encode()

    def from_db_value(self, value: str | None, expression: Any, connection: Any) -> str | None:
        if value is None:
            return value
        return decrypt_text(value, associated_data=self.associated_data())

    # No to_python override: it runs on user input during full_clean(), and decrypting
    # attacker-supplied text there is both pointless and an oracle.

    def get_prep_value(self, value: Any) -> Any:
        value = super().get_prep_value(value)
        if value is None:
            return value
        return encrypt_text(str(value), associated_data=self.associated_data())
