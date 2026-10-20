from __future__ import annotations

import argparse
import re
from pathlib import Path

APP_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,28}[a-z0-9])?$")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set the Fly app name in fly.toml.")
    parser.add_argument("app_name", help="Globally unique Fly app name")
    args = parser.parse_args()
    if not APP_NAME_PATTERN.fullmatch(args.app_name):
        parser.error("Use 3-30 lowercase letters, digits, or internal hyphens.")

    path = Path(__file__).resolve().parents[1] / "fly.toml"
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'^app = "[^"]+"$',
        f'app = "{args.app_name}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise RuntimeError("Could not find the app setting in fly.toml.")
    path.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Configured Fly app: {args.app_name}")


if __name__ == "__main__":
    main()
