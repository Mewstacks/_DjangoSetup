"""Print production secrets to stdout (never to a file; pipe them into your secret store).

    python scripts/generate_production_secrets.py
    python scripts/generate_production_secrets.py --key-id v2 --existing-ring '{"v1":"..."}'

The second form adds a key to an existing ring for rotation: set FIELD_ENCRYPTION_ACTIVE_KEY_ID
to the new id, run ``manage.py reencrypt_fields``, then drop the old key. Re-running without
``--existing-ring`` would mint a fresh ``v1`` and orphan every ciphertext, so that case warns.
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import sys


def generate_secrets(
    key_id: str = "v1", existing_ring: dict[str, str] | None = None
) -> dict[str, str]:
    ring = dict(existing_ring or {})
    if key_id in ring:
        raise ValueError(f"Key id {key_id!r} already exists in the ring; choose a new id.")
    ring[key_id] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    return {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "FIELD_ENCRYPTION_ACTIVE_KEY_ID": key_id,
        "FIELD_ENCRYPTION_KEYS": json.dumps(ring, separators=(",", ":")),
        "PRIVACY_HMAC_KEY": secrets.token_urlsafe(48),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-id", default="v1")
    parser.add_argument("--existing-ring", help="JSON object of the current key ring")
    args = parser.parse_args()
    ring = json.loads(args.existing_ring) if args.existing_ring else None
    if ring is None:
        print(
            "# New key ring. If data is already encrypted, use --existing-ring to rotate.",
            file=sys.stderr,
        )
    for name, value in generate_secrets(args.key_id, ring).items():
        if ring is not None and name in {"DJANGO_SECRET_KEY", "PRIVACY_HMAC_KEY"}:
            continue  # rotating the field key must not regenerate unrelated secrets
        print(f"{name}={value}")


if __name__ == "__main__":
    main()
