from __future__ import annotations

import base64
import hashlib
import hmac
import os
from functools import lru_cache
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from django.db import models

PREFIX = "enc:v1"


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


def _is_own_ciphertext(value: str) -> bool:
    """True only for a well-formed token that this application actually produced.

    The stored form is a plain string, so the "already encrypted, skip" decision must not
    trust a raw text prefix: a user could type ``enc:v1:...`` into a plaintext field and,
    with a prefix-only check, have it stored verbatim (never encrypted) or poison their own
    row on read. Require the full structure and a configured key id before treating a value
    as ciphertext; anything else is plaintext to be encrypted.
    """

    parts = value.split(":", 4)
    if len(parts) != 5:
        return False
    prefix, version, key_id, encoded_nonce, encoded_ciphertext = parts
    if f"{prefix}:{version}" != PREFIX:
        return False
    if key_id not in settings.FIELD_ENCRYPTION_KEYS:
        return False
    try:
        base64.urlsafe_b64decode(encoded_nonce)
        base64.urlsafe_b64decode(encoded_ciphertext)
    except (ValueError, TypeError):
        return False
    return True


def encrypt_text(value: str, *, associated_data: bytes = b"") -> str:
    if not value or _is_own_ciphertext(value):
        return value
    key_id = settings.FIELD_ENCRYPTION_ACTIVE_KEY_ID
    if not key_id:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_ACTIVE_KEY_ID is not configured.")
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key(key_id)).encrypt(nonce, value.encode(), associated_data)
    encoded_nonce = base64.urlsafe_b64encode(nonce).decode()
    encoded_ciphertext = base64.urlsafe_b64encode(ciphertext).decode()
    return f"{PREFIX}:{key_id}:{encoded_nonce}:{encoded_ciphertext}"


def decrypt_text(value: str, *, associated_data: bytes = b"") -> str:
    if not value or not value.startswith(f"{PREFIX}:"):
        return value
    try:
        prefix, version, key_id, encoded_nonce, encoded_ciphertext = value.split(":", 4)
        if f"{prefix}:{version}" != PREFIX:
            raise ValueError
        nonce = base64.urlsafe_b64decode(encoded_nonce)
        ciphertext = base64.urlsafe_b64decode(encoded_ciphertext)
        plaintext = AESGCM(_key(key_id)).decrypt(nonce, ciphertext, associated_data)
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


class EncryptedTextField(models.TextField):  # type: ignore[type-arg]
    description = "AES-256-GCM encrypted text"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("editable", True)
        super().__init__(*args, **kwargs)

    def associated_data(self) -> bytes:
        """Bind each ciphertext to the column it belongs to.

        Without this, GCM authenticates the bytes but not their location, so anyone with
        write access to the database can move a ciphertext from one model or column into
        another and it still decrypts cleanly. Row identity is deliberately not part of
        the binding: the primary key is not available when Django hydrates a field from
        a query result, so a same-column row swap remains possible.
        """

        model = getattr(self, "model", None)
        if model is None:
            return b""
        return f"{model._meta.label_lower}:{self.attname}".encode()

    def from_db_value(self, value: str | None, expression: Any, connection: Any) -> str | None:
        if value is None:
            return value
        return decrypt_text(value, associated_data=self.associated_data())

    def to_python(self, value: Any) -> Any:
        if value is None or not isinstance(value, str):
            return value
        return decrypt_text(value, associated_data=self.associated_data())

    def get_prep_value(self, value: Any) -> Any:
        value = super().get_prep_value(value)
        if value is None:
            return value
        return encrypt_text(str(value), associated_data=self.associated_data())
