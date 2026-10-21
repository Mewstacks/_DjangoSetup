"""Encrypt every Temporal payload so personal data never sits in workflow history in the clear.

Workflow histories are visible to anyone with access to the Temporal UI or database, and they
are retained for days. Flows should pass identifiers, not documents, but a mistake must not
become a leak: this codec seals *all* payloads (inputs, results, signals, memo, failures) with
AES-256-GCM under a subkey derived from the field-encryption key ring (separate purpose from
field encryption, via HKDF), and records the key id so rotation keeps old histories readable.

Headers stay readable on purpose (they carry only ids for log correlation), which also lets
operators see which organization a run belongs to.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from temporalio.api.common.v1 import Payload
from temporalio.converter import PayloadCodec

ENCODING = b"binary/platform-encrypted"
KEY_ID_METADATA = "platform-key-id"
HKDF_PURPOSE = b"saas/temporal-payload/v1"
AAD = b"temporal-payload"


class EncryptionCodec(PayloadCodec):
    def __init__(
        self,
        key_ring: dict[str, bytes] | None = None,
        active_key_id: str = "",
        *,
        allow_plaintext: bool | None = None,
    ) -> None:
        # Tests inject a ring; production derives keys lazily from Django settings.
        self._ring = key_ring
        self._active = active_key_id
        self._allow_plaintext = allow_plaintext

    def _plaintext_allowed(self) -> bool:
        if self._allow_plaintext is not None:
            return self._allow_plaintext
        from django.conf import settings

        return bool(settings.TEMPORAL_ALLOW_PLAINTEXT_PAYLOADS)

    def _key(self, key_id: str) -> bytes:
        if self._ring is not None:
            return self._ring[key_id]
        from apps.common.encryption import derive_key

        return derive_key(key_id, HKDF_PURPOSE)

    def _active_id(self) -> str:
        if self._ring is not None:
            return self._active
        from django.conf import settings

        return str(settings.FIELD_ENCRYPTION_ACTIVE_KEY_ID)

    async def encode(self, payloads: Sequence[Payload]) -> list[Payload]:
        key_id = self._active_id()
        key = AESGCM(self._key(key_id))
        sealed: list[Payload] = []
        for payload in payloads:
            nonce = os.urandom(12)
            body = nonce + key.encrypt(nonce, payload.SerializeToString(), AAD)
            sealed.append(
                Payload(
                    metadata={"encoding": ENCODING, KEY_ID_METADATA: key_id.encode()},
                    data=body,
                )
            )
        return sealed

    async def decode(self, payloads: Sequence[Payload]) -> list[Payload]:
        opened: list[Payload] = []
        for payload in payloads:
            if payload.metadata.get("encoding") != ENCODING:
                # The key is also what authenticates a payload: whoever can reach the Temporal
                # frontend can start an activity, but only this deployment can seal its input.
                # Accepting an unsealed payload would let that caller run actions as anyone.
                if self._plaintext_allowed():
                    opened.append(payload)  # history from before encryption was switched on
                    continue
                raise ValueError("Temporal payload is not sealed; refusing to read it.")
            key_id = payload.metadata[KEY_ID_METADATA].decode()
            nonce, ciphertext = payload.data[:12], payload.data[12:]
            try:
                plain = AESGCM(self._key(key_id)).decrypt(nonce, ciphertext, AAD)
            except InvalidTag as exc:
                raise ValueError("Temporal payload failed authentication.") from exc
            restored = Payload()
            restored.ParseFromString(plain)
            opened.append(restored)
        return opened
