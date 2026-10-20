from __future__ import annotations

import base64
import json
import secrets


def generate_secrets() -> dict[str, str]:
    key_id = "v1"
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    return {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "FIELD_ENCRYPTION_ACTIVE_KEY_ID": key_id,
        "FIELD_ENCRYPTION_KEYS": json.dumps({key_id: key}, separators=(",", ":")),
        "PRIVACY_HMAC_KEY": secrets.token_urlsafe(48),
    }


def main() -> None:
    for name, value in generate_secrets().items():
        print(f"{name}={value}")


if __name__ == "__main__":
    main()
