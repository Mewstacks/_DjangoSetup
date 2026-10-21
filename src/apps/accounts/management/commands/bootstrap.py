"""Make a fresh clone usable: a verified administrator, an organization and an API key.

    manage.py bootstrap                                  # admin@example.com, organization "Acme"
    manage.py bootstrap --email you@example.com --org "My Company" --json

``createsuperuser`` alone leaves you with an account that cannot sign in (the e-mail is not
verified, and verification is mandatory), no organization to act in and no key to call the API
with. This does the three things, idempotently, and prints what it made. It only runs with local
settings: it creates credentials, and it prints them once.
"""

from __future__ import annotations

import json
import secrets
from datetime import timedelta
from typing import Any

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User
from apps.actions.registry import known_scopes
from apps.apikeys.models import ApiKey
from apps.organizations.models import Membership, Organization


class Command(BaseCommand):
    help = "Create a verified superuser, an organization and an API key for local development."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--email", default="admin@example.com")
        parser.add_argument("--org", default="Acme", help="Organization name")
        parser.add_argument("--password", help="Default: generated, shown once")
        parser.add_argument("--no-key", action="store_true", help="Do not issue an API key")
        parser.add_argument("--json", action="store_true", help="Print the result as JSON")

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEV_TOOLS_ALLOWED:
            raise CommandError("bootstrap creates credentials; it only runs with local settings.")
        email = options["email"].strip().casefold()
        password: str | None = options["password"]

        user = User.objects.filter(email__iexact=email).first()
        created = user is None
        if user is None:
            password = password or secrets.token_urlsafe(16)
            user = User.objects.create_superuser(email=email, password=password)
        else:
            if password:
                user.set_password(password)
            user.is_staff = user.is_superuser = True
            user.save()
        EmailAddress.objects.update_or_create(
            user=user, email=user.email, defaults={"primary": True, "verified": True}
        )

        name = options["org"].strip()
        slug = slugify(name) or "acme"
        organization, _ = Organization.objects.get_or_create(slug=slug, defaults={"name": name})
        Membership.objects.update_or_create(
            organization=organization, user=user, defaults={"role": Membership.Role.OWNER}
        )

        secret = ""
        if not options["no_key"]:
            _, secret = ApiKey.issue(
                user=user,
                organization=organization,
                label="bootstrap",
                scopes=sorted(known_scopes()),
                expires_at=timezone.now() + timedelta(days=30),
            )

        result = {
            "email": user.email,
            "password": password if created or options["password"] else "(unchanged)",
            "organization": organization.slug,
            "organization_id": str(organization.pk),
            "api_key": secret,
            "created_user": created,
        }
        if options["json"]:
            self.stdout.write(json.dumps(result))
            return
        self.stdout.write(f"user          {result['email']}  (password: {result['password']})")
        self.stdout.write(f"organization  {result['organization']}  ({result['organization_id']})")
        if secret:
            self.stdout.write(f"api key       {secret}   (30 days; shown once)")
