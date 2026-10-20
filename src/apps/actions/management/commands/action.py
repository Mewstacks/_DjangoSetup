"""Run or list actions from the shell: ``manage.py action list`` / ``manage.py action run``."""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.actions.context import build_context
from apps.actions.registry import REGISTRY
from apps.actions.runtime import invoke
from apps.common.exceptions import DomainError


class Command(BaseCommand):
    help = "List registered actions, or run one as a user in an organization."

    def add_arguments(self, parser: Any) -> None:
        sub = parser.add_subparsers(dest="mode", required=True)
        sub.add_parser("list", help="Print every action with its scope.")
        run = sub.add_parser("run", help="Run one action.")
        run.add_argument("name")
        run.add_argument("--as", dest="email", required=True, help="Acting user's e-mail")
        run.add_argument("--org", required=True, help="Organization slug or id")
        run.add_argument("--json", default="{}", help="Input as a JSON object")
        run.add_argument("--idempotency-key")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["mode"] == "list":
            for spec in sorted(REGISTRY.values(), key=lambda s: s.name):
                kind = "write" if spec.write else "read "
                self.stdout.write(f"{spec.name:32} {kind} {spec.scope:20} {sorted(spec.channels)}")
            return

        from apps.accounts.models import User
        from apps.organizations.models import Organization

        user = User.objects.filter(email__iexact=options["email"]).first()
        if user is None:
            raise CommandError("No such user.")
        lookup = options["org"]
        organization = (
            Organization.objects.filter(slug=lookup).first()
            or Organization.objects.filter(pk=lookup).first()
        )
        if organization is None:
            raise CommandError("No such organization.")
        try:
            payload = json.loads(options["json"])
            ctx = build_context(user=user, organization=organization, channel="cli")
            output, replayed = invoke(
                options["name"], ctx, payload, idempotency_key=options["idempotency_key"]
            )
        except json.JSONDecodeError as exc:
            raise CommandError("--json is not valid JSON.") from exc
        except DomainError as error:
            raise CommandError(f"{error.code}: {error.payload()}") from error
        self.stdout.write(json.dumps({"replayed": replayed, "result": output}, indent=2))
