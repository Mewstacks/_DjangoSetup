"""Print what the ANPD's incident communication form asks for, from the recorded incident.

    manage.py privacy_incident_export INC-2026-001            # JSON on stdout
    manage.py privacy_incident_export INC-2026-001 --format md

Resolution CD/ANPD 15/2024 lists the content of the communication (what happened, which data
and how many people, the risks, the measures taken, when the controller learned of it, who the
DPO is). This command assembles those answers; it does not send anything and it does not decide
whether the incident must be communicated (that is the DPO's and counsel's call). Check the
current form on the ANPD's site before filing: the fields here follow the Resolution, not a
particular version of the form.
"""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.privacy.models import PersonalDataIncident


def build(incident: PersonalDataIncident) -> dict[str, Any]:
    def when(value: Any) -> str | None:
        return value.isoformat() if value else None

    return {
        "reference": incident.reference,
        "controller": {
            "name": settings.PRIVACY_CONTROLLER_NAME,
            "id": settings.PRIVACY_CONTROLLER_ID,
            "small_agent": settings.PRIVACY_SMALL_AGENT,
        },
        "dpo": {
            "name": settings.DPO_NAME,
            "email": settings.DPO_EMAIL,
            "contact_url": settings.DPO_CONTACT_URL,
        },
        "incident": {
            "summary": incident.summary,
            "contains_personal_data": incident.contains_personal_data,
            "relevant_risk_or_harm": incident.relevant_risk_or_harm,
            "data_categories": incident.data_categories,
            "approximate_subject_count": incident.approximate_subject_count,
            "risk_assessment": incident.risk_assessment,
            "measures_taken": incident.measures_taken,
        },
        "dates": {
            "discovered_at": when(incident.discovered_at),
            "confirmed_at": when(incident.confirmed_at),
            "notification_deadline_at": when(incident.notification_deadline_at),
            "subjects_deadline_at": when(incident.subjects_deadline_at),
            "anpd_notified_at": when(incident.anpd_notified_at),
            "complement_deadline_at": when(incident.complement_deadline_at),
            "subjects_notified_at": when(incident.subjects_notified_at),
        },
        "retain_until": when(incident.retain_until),
    }


def as_markdown(data: dict[str, Any]) -> str:
    lines = [f"# Incident {data['reference']}", ""]
    for section in ("controller", "dpo", "incident", "dates"):
        lines += [f"## {section}", ""]
        lines += [f"- **{key}**: {value}" for key, value in data[section].items()]
        lines.append("")
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Assemble the ANPD incident communication content from a recorded incident."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("reference")
        parser.add_argument("--format", choices=("json", "md"), default="json")

    def handle(self, *args: Any, **options: Any) -> None:
        incident = PersonalDataIncident.objects.filter(reference=options["reference"]).first()
        if incident is None:
            raise CommandError(f"No incident with reference {options['reference']!r}.")
        data = build(incident)
        self.stdout.write(
            as_markdown(data)
            if options["format"] == "md"
            else json.dumps(data, indent=2, ensure_ascii=False)
        )
