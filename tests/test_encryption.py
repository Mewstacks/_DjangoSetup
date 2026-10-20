from __future__ import annotations

import base64

import pytest
from django.core.exceptions import SuspiciousOperation
from django.test import override_settings

from apps.common.encryption import (
    EncryptedTextField,
    _key,
    blind_index,
    decrypt_text,
    encrypt_text,
)
from apps.privacy.models import DataSubjectRequest, PersonalDataIncident

KEY_ONE = base64.urlsafe_b64encode(b"a" * 32).decode()
KEY_TWO = base64.urlsafe_b64encode(b"b" * 32).decode()


def test_aes_gcm_round_trip_is_randomized_and_authenticated() -> None:
    with override_settings(
        FIELD_ENCRYPTION_ACTIVE_KEY_ID="one",
        FIELD_ENCRYPTION_KEYS={"one": KEY_ONE},
    ):
        _key.cache_clear()
        first = encrypt_text("private value")
        second = encrypt_text("private value")
        assert first != second
        assert first.startswith("enc:v1:one:")
        assert decrypt_text(first) == "private value"

        tampered = first[:-1] + ("A" if first[-1] != "A" else "B")
        with pytest.raises(SuspiciousOperation):
            decrypt_text(tampered)


def test_old_ciphertext_remains_decryptable_during_rotation() -> None:
    with override_settings(
        FIELD_ENCRYPTION_ACTIVE_KEY_ID="one",
        FIELD_ENCRYPTION_KEYS={"one": KEY_ONE},
    ):
        _key.cache_clear()
        ciphertext = encrypt_text("rotate me")

    with override_settings(
        FIELD_ENCRYPTION_ACTIVE_KEY_ID="two",
        FIELD_ENCRYPTION_KEYS={"one": KEY_ONE, "two": KEY_TWO},
    ):
        _key.cache_clear()
        assert decrypt_text(ciphertext) == "rotate me"
        assert encrypt_text("new value").startswith("enc:v1:two:")


def test_ciphertext_cannot_be_moved_between_columns() -> None:
    details = DataSubjectRequest._meta.get_field("details")
    summary = PersonalDataIncident._meta.get_field("summary")
    assert isinstance(details, EncryptedTextField)
    assert isinstance(summary, EncryptedTextField)
    assert details.associated_data() != summary.associated_data()

    ciphertext = details.get_prep_value("private note")
    assert details.from_db_value(ciphertext, None, None) == "private note"
    with pytest.raises(SuspiciousOperation):
        summary.from_db_value(ciphertext, None, None)


def test_value_that_only_looks_like_a_token_is_still_encrypted() -> None:
    with override_settings(
        FIELD_ENCRYPTION_ACTIVE_KEY_ID="one",
        FIELD_ENCRYPTION_KEYS={"one": KEY_ONE},
    ):
        _key.cache_clear()
        # Prefix-shaped but names a key the ring does not have: must be treated as plaintext
        # and encrypted for real, not passed through verbatim.
        forged = "enc:v1:ghost:AAAA:AAAA"
        stored = encrypt_text(forged)
        assert stored.startswith("enc:v1:one:")
        assert decrypt_text(stored) == forged


def test_unknown_key_id_on_read_is_a_handled_error_not_a_500() -> None:
    with override_settings(
        FIELD_ENCRYPTION_ACTIVE_KEY_ID="one",
        FIELD_ENCRYPTION_KEYS={"one": KEY_ONE},
    ):
        _key.cache_clear()
        # A stored token naming an unknown key id used to raise ImproperlyConfigured (500);
        # it must now surface as SuspiciousOperation (400) so one poisoned row cannot break
        # every subsequent read of the owner's data or the admin changelist.
        with pytest.raises(SuspiciousOperation):
            decrypt_text("enc:v1:ghost:AAAA:AAAA")


@override_settings(PRIVACY_HMAC_KEY="independent-test-hmac-key")
def test_blind_index_is_normalized_and_namespaced() -> None:
    assert blind_index(" User@Example.COM ", namespace="email") == blind_index(
        "user@example.com",
        namespace="email",
    )
    assert blind_index("user@example.com", namespace="email") != blind_index(
        "user@example.com",
        namespace="phone",
    )
