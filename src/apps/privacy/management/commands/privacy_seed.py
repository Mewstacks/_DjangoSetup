"""Create the baseline purposes (and, with --notice, a first notice) if they are missing."""

from __future__ import annotations

import hashlib
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.privacy.baseline import BASELINE_PURPOSES
from apps.privacy.models import PrivacyNotice, ProcessingPurpose


class Command(BaseCommand):
    help = "Create baseline processing purposes. Review them with your DPO before launch."

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
                "notice published; replace the checksum with the hash of the real document"
            )
