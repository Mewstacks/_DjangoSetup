"""Verify the audit hash chains. Exit code 1 if any chain is broken - wire it into monitoring.

manage.py audit_verify                        # recompute every chain
manage.py audit_verify --json > heads.json    # record each head outside the database
manage.py audit_verify --expect heads.json    # ...and later prove no newest events vanished
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.audit.integrity import heads, verify_all, verify_chain


class Command(BaseCommand):
    help = "Recompute every audit hash and report tampering, gaps and broken links."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--org", help="Verify only this organization id's chain")
        parser.add_argument("--print-anchor", action="store_true", help="Print each head hash")
        parser.add_argument("--json", action="store_true", help="Print the heads as JSON")
        parser.add_argument("--expect", help="JSON file of heads recorded earlier (--json output)")

    def handle(self, *args: Any, **options: Any) -> None:
        expected = None
        if options["expect"]:
            try:
                expected = json.loads(Path(options["expect"]).read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise CommandError(f"Cannot read --expect file: {error}") from error
        if options["org"]:
            expect = (expected or {}).get(options["org"])
            reports = [verify_chain(options["org"], expect=expect)]
        else:
            reports = verify_all(expected)
        if options["json"]:
            self.stdout.write(json.dumps(heads(reports), indent=2, sort_keys=True))
            if any(not report.ok for report in reports):
                raise SystemExit(1)
            return
        broken = 0
        for report in reports:
            state = "ok" if report.ok else "BROKEN"
            self.stdout.write(f"{report.chain_key:40} {report.checked:>8} events  {state}")
            for problem in report.problems[:20]:
                self.stdout.write(f"    {problem}")
            if options["print_anchor"] and report.last_hash:
                self.stdout.write(f"    head seq={report.last_seq} hash={report.last_hash}")
            broken += 0 if report.ok else 1
        if not reports:
            self.stdout.write("no chained events yet")
        if broken:
            raise SystemExit(1)
