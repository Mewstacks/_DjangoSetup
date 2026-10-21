"""Remove the ``examples`` app (the Notes reference resource) before you build your product.

    python scripts/remove_example.py            # preview: what would go, what still mentions it
    python scripts/remove_example.py --apply

It deletes ``src/apps/examples``, takes it out of ``LOCAL_APPS`` and the API router, and then
lists every remaining file that still uses notes. Those are tests (and the smoke script) that use
Notes as a convenient tenant resource; port them to your own resource instead of deleting them.
``python manage.py scaffold resource ...`` generates a test file that shows the shape.

Afterwards regenerate the committed files: ``python manage.py actions_catalog``,
``python scripts/check_openapi.py --write``, ``python scripts/gen_docs.py``.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MENTIONS = re.compile(r"apps\.examples|\bnotes\.|\bNote\b|notes_|/notes/|examples\.note")


def edits(root: Path) -> list[tuple[Path, str, str]]:
    return [
        (root / "src/config/settings/base.py", '    "apps.examples",\n', ""),
        (root / "src/config/urls_api.py", "from apps.examples.api import NoteViewSet\n", ""),
        (
            root / "src/config/urls_api.py",
            'router.register("notes", NoteViewSet, basename="note")\n',
            "",
        ),
    ]


def remaining_mentions(root: Path) -> dict[str, int]:
    found: dict[str, int] = {}
    for folder in ("src", "tests", "scripts"):
        for path in sorted((root / folder).rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            if relative.startswith("src/apps/examples/") or relative.endswith("remove_example.py"):
                continue
            count = len(MENTIONS.findall(path.read_text(encoding="utf-8")))
            if count:
                found[relative] = count
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root: Path = args.root

    app = root / "src/apps/examples"
    print(f"{'delete' if app.exists() else 'absent'} {app.relative_to(root).as_posix()}/")
    if args.apply and app.exists():
        shutil.rmtree(app)
    for path, old, new in edits(root):
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        present = old in text
        label = "edit  " if present else "done  "
        print(f"{label} {path.relative_to(root).as_posix()}: {old.strip()}")
        if args.apply and present:
            path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

    mentions = remaining_mentions(root)
    print(f"\n{len(mentions)} file(s) still mention the example resource:")
    for relative, count in mentions.items():
        print(f"  {count:>3}  {relative}")
    print("\nPort those to your own resource, then regenerate the committed files.")
    print("Applied." if args.apply else "Preview only: add --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
