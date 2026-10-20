"""Check configuration and dependencies; exit non-zero when something is broken."""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand

from apps.observability.checks import FAIL, WARN, run_all

MARK = {"ok": "ok  ", "info": "info", "warn": "WARN", "fail": "FAIL"}


class Command(BaseCommand):
    help = "Check the deployment: database, cache, keys, HTTPS, flows, MCP, audit chain."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--strict", action="store_true", help="Exit 1 on warnings too")
        parser.add_argument("--json", action="store_true", help="Machine-readable output")

    def handle(self, *args: Any, **options: Any) -> None:
        results = run_all()
        if options["json"]:
            self.stdout.write(json.dumps([r.__dict__ for r in results], indent=2))
        else:
            for check in results:
                self.stdout.write(f"[{MARK[check.status]}] {check.name:14} {check.detail}")
        failed = [c for c in results if c.status == FAIL]
        warned = [c for c in results if c.status == WARN]
        if failed or (options["strict"] and warned):
            raise SystemExit(1)
