from __future__ import annotations

import argparse
import base64
import secrets
from pathlib import Path


def random_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a safe local .env file.")
    parser.add_argument(
        "--sqlite",
        action="store_true",
        help="Use SQLite instead of local PostgreSQL",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing .env")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    if target.exists() and not args.force:
        parser.error(".env already exists; use --force to replace it.")

    content = (root / ".env.example").read_text(encoding="utf-8")
    content = content.replace(
        "local-only-change-me-never-use-in-production",
        secrets.token_urlsafe(64),
    )
    content = content.replace("REPLACE_WITH_BASE64_32_BYTE_KEY", random_key())
    content = content.replace(
        "REPLACE_WITH_AN_INDEPENDENT_RANDOM_SECRET",
        secrets.token_urlsafe(48),
    )
    if args.sqlite:
        content = content.replace("DB_ENGINE=postgresql", "DB_ENGINE=sqlite")
    target.write_text(content, encoding="utf-8", newline="\n")
    print(f"Created {target}")


if __name__ == "__main__":
    main()
