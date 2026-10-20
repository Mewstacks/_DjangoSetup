"""Generate the record of processing operations (RoPA, LGPD art. 37) from the data catalog."""

from __future__ import annotations

import csv
import json
import sys
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.privacy.catalog import CATALOG
from apps.privacy.models import ProcessingPurpose, SubProcessor


def build() -> dict[str, Any]:
    purposes = {p.code: p for p in ProcessingPurpose.objects.all()}
    operations = []
    for item in sorted(CATALOG.values(), key=lambda c: c.label):
        if not item.personal:
            continue
        purpose = purposes.get(item.purpose)
        operations.append(
            {
                "table": item.label,
                "personal_fields": {name: cat.value for name, cat in item.fields.items()},
                "sensitive": item.sensitive,
                "purpose": item.purpose,
                "purpose_name": purpose.name if purpose else None,
                "lawful_basis": purpose.lawful_basis if purpose else None,
                "retention_days": purpose.retention_days if purpose else None,
                "on_erase": item.on_erase,
                "kept_because": item.reason if item.on_erase == "keep" else "",
            }
        )
    return {
        "controller": {
            "name": settings.PRIVACY_CONTROLLER_NAME,
            "id": settings.PRIVACY_CONTROLLER_ID,
        },
        "dpo": {"name": settings.DPO_NAME, "email": settings.DPO_EMAIL},
        "operations": operations,
        "sub_processors": [
            {
                "name": s.name,
                "purpose": s.purpose,
                "country": s.country,
                "transfer_mechanism": s.transfer_mechanism,
            }
            for s in SubProcessor.objects.filter(active=True)
        ],
    }


class Command(BaseCommand):
    help = "Print the record of processing operations as JSON or CSV."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--format", choices=["json", "csv"], default="json")

    def handle(self, *args: Any, **options: Any) -> None:
        ropa = build()
        if options["format"] == "json":
            self.stdout.write(json.dumps(ropa, indent=2, ensure_ascii=False))
            return
        writer = csv.writer(sys.stdout)
        writer.writerow(
            [
                "table",
                "purpose",
                "lawful_basis",
                "retention_days",
                "sensitive",
                "on_erase",
                "fields",
            ]
        )
        for op in ropa["operations"]:
            writer.writerow(
                [
                    op["table"],
                    op["purpose"],
                    op["lawful_basis"],
                    op["retention_days"],
                    op["sensitive"],
                    op["on_erase"],
                    ";".join(op["personal_fields"]),
                ]
            )
