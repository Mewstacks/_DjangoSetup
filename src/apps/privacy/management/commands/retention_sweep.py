"""Run the retention sweep by hand; --dry-run reports what would change and changes nothing."""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand

from apps.privacy.retention import sweep


class Command(BaseCommand):
    help = "Delete or anonymize personal data past its purpose's retention period."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(json.dumps(sweep(dry_run=options["dry_run"]), indent=2, default=str))
