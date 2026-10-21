"""Rotating the secrets that sit outside the field-encryption ring must not lock anyone out."""

from __future__ import annotations

from io import StringIO

import pytest
from allauth.mfa.models import Authenticator
from django.core.exceptions import SuspiciousOperation
from django.core.management import call_command
from django.test import override_settings

from apps.accounts.models import User
from apps.apikeys.authentication import authenticate_key
from apps.apikeys.models import ApiKey
from apps.common import encryption
from apps.organizations.models import Membership, Organization
from apps.privacy.models import DataSubject

pytestmark = pytest.mark.django_db

OLD = "old-independent-hmac-key-0123456789abcdef"
NEW = "new-independent-hmac-key-fedcba9876543210"


def test_api_keys_survive_a_privacy_hmac_rotation_and_move_to_the_new_key(
    user: User, organization: Organization, membership: Membership
) -> None:
    with override_settings(PRIVACY_HMAC_KEY=OLD):
        key, raw = ApiKey.issue(
            user=user, organization=organization, label="ci", scopes=["notes:read"]
        )
        old_index = key.secret_index
        assert authenticate_key(raw) is not None

    with override_settings(PRIVACY_HMAC_KEY=NEW, PRIVACY_HMAC_KEYS_PREVIOUS=[]):
        assert authenticate_key(raw) is None  # without the previous key the old index is lost

    with override_settings(PRIVACY_HMAC_KEY=NEW, PRIVACY_HMAC_KEYS_PREVIOUS=[OLD]):
        assert authenticate_key(raw) is not None  # found under the old key...
        key.refresh_from_db()
        assert key.secret_index != old_index  # ...and rewritten under the new one

    with override_settings(PRIVACY_HMAC_KEY=NEW, PRIVACY_HMAC_KEYS_PREVIOUS=[]):
        assert authenticate_key(raw) is not None  # the previous key can now be dropped


def test_a_wrong_secret_never_matches_under_any_candidate_key(
    user: User, organization: Organization, membership: Membership
) -> None:
    with override_settings(PRIVACY_HMAC_KEY=NEW, PRIVACY_HMAC_KEYS_PREVIOUS=[OLD]):
        _, raw = ApiKey.issue(
            user=user, organization=organization, label="ci", scopes=["notes:read"]
        )
        prefix, public_id, _ = raw.split("_")
        assert authenticate_key(f"{prefix}_{public_id}_{'0' * 64}") is None


def test_data_subjects_are_found_and_reindexed_after_a_rotation() -> None:
    with override_settings(PRIVACY_HMAC_KEY=OLD):
        subject = DataSubject.for_email("Person@Example.com")
        old_index = subject.email_index
    with override_settings(PRIVACY_HMAC_KEY=NEW, PRIVACY_HMAC_KEYS_PREVIOUS=[OLD]):
        again = DataSubject.for_email("person@example.com")
        assert again.pk == subject.pk and again.email_index != old_index
        assert DataSubject.objects.count() == 1  # not a second record for the same person


def test_the_blind_index_candidates_put_the_current_key_first() -> None:
    with override_settings(PRIVACY_HMAC_KEY=NEW, PRIVACY_HMAC_KEYS_PREVIOUS=[OLD, NEW, ""]):
        candidates = encryption.blind_index_candidates("x", namespace="n")
    assert len(candidates) == 2 and len(set(candidates)) == 2
    with override_settings(PRIVACY_HMAC_KEY=NEW):
        assert candidates[0] == encryption.blind_index("x", namespace="n")


def test_reencrypt_fields_also_reseals_mfa_secrets(user: User) -> None:
    from apps.accounts.adapters import MFA_AAD

    ring = {
        "k1": "MTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTE=",
        "k2": "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjI=",
    }
    with override_settings(FIELD_ENCRYPTION_KEYS=ring, FIELD_ENCRYPTION_ACTIVE_KEY_ID="k1"):
        encryption.clear_key_cache()
        sealed = encryption.encrypt_text("TOTPSEED", associated_data=MFA_AAD)
        row = Authenticator.objects.create(
            user=user, type=Authenticator.Type.TOTP, data={"secret": sealed}
        )
        assert sealed.startswith("enc:v2:k1:")
    with override_settings(FIELD_ENCRYPTION_KEYS=ring, FIELD_ENCRYPTION_ACTIVE_KEY_ID="k2"):
        encryption.clear_key_cache()
        out = StringIO()
        call_command("reencrypt_fields", stdout=out)
        row.refresh_from_db()
        assert row.data["secret"].startswith("enc:v2:k2:")
        assert encryption.decrypt_text(row.data["secret"], associated_data=MFA_AAD) == "TOTPSEED"
    encryption.clear_key_cache()


def test_the_mfa_adapter_refuses_a_plaintext_seed() -> None:
    from apps.accounts.adapters import MFAAdapter

    with pytest.raises(SuspiciousOperation):
        MFAAdapter().decrypt("JBSWY3DPEHPK3PXP")


def test_secret_key_fallbacks_keep_old_sessions_valid() -> None:
    from django.core import signing

    with override_settings(SECRET_KEY="a-previous-secret-key-for-signing-0123456789abcdef"):
        token = signing.dumps({"u": 1})
    with override_settings(
        SECRET_KEY="the-current-secret-key-for-signing-0123456789abcdef",
        SECRET_KEY_FALLBACKS=["a-previous-secret-key-for-signing-0123456789abcdef"],
    ):
        assert signing.loads(token) == {"u": 1}
    with (
        override_settings(SECRET_KEY="the-current-secret-key-for-signing-0123456789abcdef"),
        pytest.raises(signing.BadSignature),
    ):
        signing.loads(token)
