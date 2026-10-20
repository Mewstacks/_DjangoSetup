"""Flip a flag from the shell: ``manage.py flag notes-v2 on --org acme``."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.flags.models import Flag, FlagRule


class Command(BaseCommand):
    help = "Create a flag, set its default, or add a user/organization/percentage rule."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("key")
        parser.add_argument("state", choices=["on", "off"])
        parser.add_argument("--org", help="Organization slug")
        parser.add_argument("--user", help="User e-mail")
        parser.add_argument("--percent", type=int, help="Share of callers, 0-100")

    def handle(self, *args: Any, **options: Any) -> None:
        enabled = options["state"] == "on"
        flag, _ = Flag.objects.get_or_create(key=options["key"])
        targets = [options["org"], options["user"], options["percent"]]
        if sum(t is not None for t in targets) > 1:
            raise CommandError("Pick one of --org, --user, --percent.")
        if options["org"]:
            from apps.organizations.models import Organization

            org = Organization.objects.filter(slug=options["org"]).first()
            if org is None:
                raise CommandError("No such organization.")
            FlagRule.objects.update_or_create(
                flag=flag, organization=org, defaults={"enabled": enabled}
            )
        elif options["user"]:
            from apps.accounts.models import User

            user = User.objects.filter(email__iexact=options["user"]).first()
            if user is None:
                raise CommandError("No such user.")
            FlagRule.objects.update_or_create(flag=flag, user=user, defaults={"enabled": enabled})
        elif options["percent"] is not None:
            if not 0 <= options["percent"] <= 100:
                raise CommandError("--percent must be between 0 and 100.")
            FlagRule.objects.update_or_create(
                flag=flag,
                user=None,
                organization=None,
                defaults={"percentage": options["percent"], "enabled": enabled},
            )
        else:
            flag.default_enabled = enabled
            flag.save(update_fields=["default_enabled", "updated_at"])
        self.stdout.write(f"{flag.key}: ok")
