"""Generate a tenant resource that already follows the platform's rules.

    manage.py scaffold resource invoices Invoice --fields 'title:str,notes:text,amount:decimal'
    manage.py scaffold resource invoices Invoice --fields 'title:str' --dry-run

Field types: str, text (encrypted), int, bool, decimal, datetime. Nothing is overwritten. The
generated LGPD entry is a safe default with a list of decisions in its docstring: read it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from devtools import scaffold


class Command(BaseCommand):
    help = "Scaffold a tenant resource (model, service, actions, undo, events, MCP, LGPD, tests)."

    def add_arguments(self, parser: Any) -> None:
        sub = parser.add_subparsers(dest="kind", required=True)
        resource = sub.add_parser("resource", help="A tenant-scoped model with five actions")
        resource.add_argument("app", help="snake_case plural, for example invoices")
        resource.add_argument("model", help="CamelCase singular, for example Invoice")
        resource.add_argument("--fields", required=True, help="name:type,name:type")
        resource.add_argument("--dry-run", action="store_true", help="List the files only")

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEV_TOOLS_ALLOWED:
            raise CommandError("scaffold writes source files; it only runs with local settings.")
        try:
            fields = scaffold.parse_fields(options["fields"])
            files = scaffold.render(options["app"], options["model"], fields)
            if options["dry_run"]:
                for name in files:
                    self.stdout.write(name)
                return
            root = Path(settings.PROJECT_ROOT)
            written = scaffold.write(root, files, app=options["app"])
        except scaffold.ScaffoldError as error:
            raise CommandError(str(error)) from error
        for name in written:
            self.stdout.write(f"wrote {name}")
        self.stdout.write("")
        for number, step in enumerate(scaffold.NEXT_STEPS, 1):
            self.stdout.write(f"{number}. {step.format(app=options['app'])}")
