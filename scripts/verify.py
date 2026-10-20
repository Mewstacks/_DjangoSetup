"""Run the quality gate (G) locally: the same steps CI runs.

    python scripts/verify.py            # full gate
    python scripts/verify.py --fast     # skip mypy and the production deploy check
    python scripts/verify.py --keep-going

Each step is a plain subprocess so a failure shows the tool's own output.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# `check --deploy` needs production settings, which refuse to boot without real-looking secrets.
# These values only satisfy the validators for the check; nothing is ever deployed with them.
def _random_looking(label: str, length: int) -> str:
    return (hashlib.sha256(label.encode()).hexdigest() * 3)[:length]


DEPLOY_CHECK_ENV = {
    "DJANGO_SETTINGS_MODULE": "config.settings.production",
    "DJANGO_SECRET_KEY": _random_looking("django", 64),
    "DJANGO_ALLOWED_HOSTS": "app.verify.test",
    "DATABASE_URL": "postgres://u:p@db.verify.test:5432/app?sslmode=require",
    "REDIS_URL": "rediss://:p@cache.verify.test:6379/0",
    "FIELD_ENCRYPTION_ACTIVE_KEY_ID": "v1",
    "FIELD_ENCRYPTION_KEYS": '{"v1": "'
    + base64.urlsafe_b64encode(hashlib.sha256(b"field-key").digest()).decode()
    + '"}',
    "PRIVACY_HMAC_KEY": _random_looking("hmac", 48),
    "TRUSTED_PROXY_COUNT": "1",
    "BUCKET_NAME": "verify-bucket",
    "SENTRY_ENABLED": "false",
}


def run(label: str, cmd: list[str], env: dict[str, str] | None = None) -> bool:
    print(f"\n==> {label}\n    $ {' '.join(cmd)}", flush=True)
    merged = {**os.environ, **(env or {})}
    result = subprocess.run(cmd, cwd=ROOT, env=merged, check=False)  # noqa: S603
    ok = result.returncode == 0
    print(f"    {'ok' if ok else 'FAILED'}", flush=True)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    args = parser.parse_args()

    py = sys.executable
    steps: list[tuple[str, list[str], dict[str, str] | None]] = [
        ("ruff lint", [py, "-m", "ruff", "check", "."], None),
        ("ruff format", [py, "-m", "ruff", "format", "--check", "."], None),
    ]
    if not args.fast:
        steps.append(("mypy", [py, "-m", "mypy", "src"], None))
    steps.append(("pytest", [py, "-m", "pytest", "-q"], None))
    steps.append(
        (
            "makemigrations --check",
            [py, "manage.py", "makemigrations", "--check", "--dry-run"],
            {"DJANGO_SETTINGS_MODULE": "config.settings.test"},
        )
    )
    if not args.fast:
        steps.append(("check --deploy", [py, "manage.py", "check", "--deploy"], DEPLOY_CHECK_ENV))

    failed: list[str] = []
    for label, cmd, env in steps:
        if not run(label, cmd, env):
            failed.append(label)
            if not args.keep_going:
                break
    print("\n" + ("GATE FAILED: " + ", ".join(failed) if failed else "GATE OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
