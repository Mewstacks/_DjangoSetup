from __future__ import annotations

import base64
import json

from scripts.generate_production_secrets import generate_secrets
from scripts.init_local import random_key


def test_secret_generators_create_independent_256_bit_field_keys() -> None:
    generated = generate_secrets()
    key_ring = json.loads(generated["FIELD_ENCRYPTION_KEYS"])
    assert len(base64.urlsafe_b64decode(key_ring["v1"])) == 32
    assert len(base64.urlsafe_b64decode(random_key())) == 32
    assert generated["DJANGO_SECRET_KEY"] != generated["PRIVACY_HMAC_KEY"]


def test_rotation_adds_a_key_without_replacing_the_existing_one() -> None:
    first = generate_secrets()
    ring = json.loads(first["FIELD_ENCRYPTION_KEYS"])
    rotated = generate_secrets("v2", ring)
    new_ring = json.loads(rotated["FIELD_ENCRYPTION_KEYS"])
    assert new_ring["v1"] == ring["v1"]
    assert set(new_ring) == {"v1", "v2"}
    assert rotated["FIELD_ENCRYPTION_ACTIVE_KEY_ID"] == "v2"
