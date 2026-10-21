"""Create the baseline purposes (and, with --notice, a first notice) if they are missing."""

from __future__ import annotations

import hashlib
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.privacy.baseline import BASELINE_PURPOSES
from apps.privacy.models import PrivacyNotice, ProcessingPurpose, SubProcessor

# The technologies this platform can run on. They are created INACTIVE: a row only appears in
# the transparency endpoint and in "who do you share with" answers once the operator confirms
# they really use that vendor and fills in the country and the transfer mechanism (LGPD art. 33,
# Res. CD/ANPD 19/2024). Publishing a vendor you do not use is as wrong as hiding one you do.
PLATFORM_SUB_PROCESSORS = (
    ("Error reporting (Sentry)", "Error and performance diagnostics, scrubbed of personal data"),
    ("Object storage (S3-compatible)", "Stored uploads and sealed data exports"),
    ("E-mail delivery (SMTP provider)", "Verification, reset and privacy-request messages"),
    ("Managed Temporal (Temporal Cloud)", "Durable workflows; payloads are encrypted by us"),
    ("Hosting and database provider", "Runs the application and stores its data"),
)


class Command(BaseCommand):
    help = "Create baseline processing purposes. Review them with your DPO before launch."

    def _seed_sub_processors(self) -> None:
        created = 0
        for name, purpose in PLATFORM_SUB_PROCESSORS:
            _, was_created = SubProcessor.objects.get_or_create(
                name=name,
                defaults={
                    "purpose": purpose,
                    "country": "",
                    "transfer_mechanism": SubProcessor.Transfer.OTHER,
                    "active": False,
                },
            )
            created += int(was_created)
        self.stdout.write(
            f"sub-processors: {created} created inactive; activate the ones you use and set "
            "the country and transfer mechanism"
        )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--notice-url", help="Publish a first notice pointing at this URL")
        parser.add_argument("--notice-version", default="1")

    def handle(self, *args: Any, **options: Any) -> None:
        created = 0
        for spec in BASELINE_PURPOSES:
            _, was_created = ProcessingPurpose.objects.get_or_create(
                code=spec["code"], defaults={k: v for k, v in spec.items() if k != "code"}
            )
            created += int(was_created)
        self.stdout.write(f"purposes: {created} created, {len(BASELINE_PURPOSES) - created} kept")
        self._seed_sub_processors()
        url = options.get("notice_url")
        if url and not PrivacyNotice.objects.exists():
            PrivacyNotice.objects.create(
                version=options["notice_version"],
                document_url=url,
                checksum_sha256=hashlib.sha256(url.encode()).hexdigest(),
                effective_at=timezone.now(),
                active=True,
            )
            self.stdout.write(
                "notice published (its checksum is the hash of the URL: a notice is immutable, "
                "so publish the next version with the hash of the real document)"
            )
