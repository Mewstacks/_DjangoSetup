"""Make this repository your product: rename it and clear the template's identity.

    python scripts/init_project.py --name "Acme Billing"           # preview
    python scripts/init_project.py --name "Acme Billing" --apply

What changes (a list of exact text replacements, shown before anything is written):
the package name and description, the OpenAPI title, the admin header, the default application
name used for cache keys and the MFA issuer, the Compose project names and the example image
name. Python packages (``apps``, ``config``) keep their names: renaming an import path buys
nothing and breaks every future merge from the template.

Nothing about security, tenancy or LGPD is touched. Run it once, right after cloning.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,38}", slug):
        raise SystemExit(f"Cannot make a name from {name!r}: use letters, digits and spaces.")
    return slug


def replacements(name: str) -> list[tuple[str, str, str]]:
    slug = slugify(name)
    short = slug.replace("-", "")[:20]
    return [
        ("pyproject.toml", 'name = "saas-django-backend"', f'name = "{slug}"'),
        (
            "pyproject.toml",
            'description = "Security-first, LGPD-aware reusable Django SaaS backend"',
            f'description = "{name}: backend"',
        ),
        ("src/config/settings/base.py", 'or "saas"\n', f'or "{short}"\n'),
        ("src/config/settings/base.py", '"TITLE": "SaaS Backend API"', f'"TITLE": "{name} API"'),
        (
            "src/config/settings/base.py",
            '"DESCRIPTION": "Versioned API for the reusable SaaS backend."',
            f'"DESCRIPTION": "Versioned API of {name}."',
        ),
        ("src/apps/common/admin.py", '"SaaS Operations"', f'"{name} Operations"'),
        ("compose.yaml", "name: saas-backend", f"name: {slug}"),
        ("deploy/compose/compose.prod.yaml", "name: app-prod", f"name: {slug}-prod"),
        ("deploy/compose/prod.env.example", "ghcr.io/you/app", f"ghcr.io/you/{slug}"),
        ("deploy/k8s/base/migrate-job.yaml", "ghcr.io/you/app@", f"ghcr.io/you/{slug}@"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True, help='Product name, for example "Acme Billing"')
    parser.add_argument("--apply", action="store_true", help="Write the changes (default: preview)")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    name = args.name.strip()
    if not 2 <= len(name) <= 40 or any(c in name for c in '"\\\n'):
        raise SystemExit("The name must be 2-40 characters, without quotes or backslashes.")

    changed = skipped = 0
    for relative, old, new in replacements(name):
        path = args.root / relative
        if not path.exists():
            print(f"skip   {relative} (not in this checkout)")
            skipped += 1
            continue
        text = path.read_text(encoding="utf-8")
        if old not in text:
            state = "done  " if new in text else "absent"
            print(f"{state} {relative}: {old[:60]!r}")
            skipped += 1
            continue
        print(f"change {relative}: {old[:50]!r} -> {new[:50]!r}")
        changed += 1
        if args.apply:
            path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    print(f"\n{changed} change(s), {skipped} already done or absent.", end=" ")
    print("Written." if args.apply else "Preview only: add --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
