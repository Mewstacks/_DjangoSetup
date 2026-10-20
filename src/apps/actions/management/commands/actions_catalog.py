"""Write (or verify) the committed action catalog: ``docs/reference/actions.json``.

The file is the reviewable record of the platform's operations - names, scopes, schemas. CI
runs ``--check`` so an action cannot be added, renamed or loosened without the diff showing up
in the pull request.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.actions.registry import REGISTRY
from apps.actions.rest import describe

DEFAULT_PATH = Path("docs/reference/actions.json")


def render() -> str:
    items = [describe(spec) for spec in sorted(REGISTRY.values(), key=lambda s: s.name)]
    return json.dumps({"actions": items}, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


class Command(BaseCommand):
    help = "Write the action catalog to a file, or fail if the committed file is stale."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--out", type=Path, default=DEFAULT_PATH)
        parser.add_argument("--check", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        target: Path = options["out"]
        rendered = render()
        if options["check"]:
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != rendered:
                raise CommandError(
                    f"{target} is out of date; run `python manage.py actions_catalog` and commit."
                )
            self.stdout.write("action catalog is up to date")
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8", newline="\n")
        self.stdout.write(f"wrote {target}")
