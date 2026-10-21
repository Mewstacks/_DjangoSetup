"""From a fresh clone to a running, usable product in one command.

    uv sync --all-extras
    python scripts/bootstrap.py                      # SQLite, admin@example.com, organization Acme
    python scripts/bootstrap.py --postgres --email you@company.com --org "My Company"

It writes a ``.env`` with fresh random secrets (never overwriting one), applies the migrations,
seeds the LGPD purposes, and creates a verified administrator, an organization and an API key.
Credentials are printed once, to this terminal. Local development only: it uses
``config.settings.local`` and refuses to touch anything else.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def step(label: str, result: subprocess.CompletedProcess[str]) -> str:
    ok = result.returncode == 0
    print(f"{'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        print(result.stdout[-2000:] + result.stderr[-2000:])
        raise SystemExit(1)
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--postgres", action="store_true", help="Use PostgreSQL (default SQLite)")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--org", default="Acme")
    parser.add_argument("--no-key", action="store_true")
    args = parser.parse_args()

    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.local"}
    if not (ROOT / ".env").exists():
        flags = [] if args.postgres else ["--sqlite"]
        step(".env with fresh secrets", run("scripts/init_local.py", *flags, env=env))
    else:
        print("ok   .env already exists (kept)")
    step("database migrated", run("manage.py", "migrate", "--noinput", env=env))
    step("LGPD purposes seeded", run("manage.py", "privacy_seed", env=env))
    command = ["manage.py", "bootstrap", "--email", args.email, "--org", args.org]
    if args.no_key:
        command.append("--no-key")
    summary = step("administrator, organization and key", run(*command, env=env))
    print()
    print(summary.rstrip())
    print()
    print("Next:")
    print("  python manage.py runserver        # then open http://localhost:8000/api/docs/")
    print("  python manage.py action list      # every action; try: action run notes.create ...")
    print("  python manage.py doctor           # is this deployment sound?")
    print("  python -m devtools.mcp            # the MCP server for your AI coding agent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
