"""Verify the audit hash chains. Exit code 1 if any chain is broken - wire it into monitoring."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.audit.integrity import verify_all, verify_chain


class Command(BaseCommand):
    help = "Recompute every audit hash and report tampering, gaps and broken links."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--org", help="Verify only this organization id's chain")
        parser.add_argument("--print-anchor", action="store_true", help="Print each head hash")

    def handle(self, *args: Any, **options: Any) -> None:
        reports = [verify_chain(options["org"])] if options["org"] else verify_all()
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
