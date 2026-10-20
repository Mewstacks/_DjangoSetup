"""Scheduled privacy work. Each job is idempotent; with Temporal off, cron runs them by name."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.core.files.storage import default_storage
from django.utils import timezone

from apps.flows.declare import job


@job("privacy.dsar_sweep", schedule="*/10 * * * *")
def dsar_sweep() -> dict[str, Any]:
    """Start the flow for verified requests that never got one (Temporal was unreachable)."""
    from apps.privacy.lifecycle import start_dsar
    from apps.privacy.models import DataSubjectRequest

    started = 0
    pending = DataSubjectRequest.objects.filter(
        status__in=[
            DataSubjectRequest.Status.RECEIVED,
            DataSubjectRequest.Status.IN_PROGRESS,
        ],
        identity_verified_at__isnull=False,
        created_at__lt=timezone.now() - timedelta(minutes=2),
    )
    for request in pending:
        started += int(start_dsar(request))
    return {"started": started}


@job("privacy.dsar_sla", schedule="5 * * * *")
def dsar_sla() -> dict[str, Any]:
    """Remind the DPO of requests at D-5, D-1 and past their deadline (once each)."""
    from apps.privacy.models import DataSubjectRequest
    from apps.privacy.services import send_reminders

    sent = 0
    for request in DataSubjectRequest.objects.exclude(status__in=list(DataSubjectRequest.TERMINAL)):
        sent += len(send_reminders(request))
    return {"reminders": sent}


@job("privacy.incident_deadlines", schedule="15 * * * *")
def incident_deadlines() -> dict[str, Any]:
    """Remind the DPO of relevant-risk incidents nearing or past the ANPD notification time."""
    from apps.privacy.models import PersonalDataIncident, PrivacyReminder
    from apps.privacy.services import notify_dpo

    now = timezone.now()
    sent = 0
    open_incidents = PersonalDataIncident.objects.filter(
        relevant_risk_or_harm=True,
        anpd_notified_at__isnull=True,
        notification_deadline_at__isnull=False,
    ).exclude(status=PersonalDataIncident.Status.CLOSED)
    for incident in open_incidents:
        left = incident.notification_deadline_at - now  # type: ignore[operator]
        kinds = []
        if left <= timedelta(days=1):
            kinds.append("due_in_1_day")
        if left <= timedelta(0):
            kinds.append("overdue")
        for kind in kinds:
            _, created = PrivacyReminder.objects.get_or_create(incident=incident, kind=kind)
            if created:
                notify_dpo(
                    f"[incident] {incident.reference}: {kind.replace('_', ' ')}",
                    f"Notify the ANPD by {incident.notification_deadline_at:%Y-%m-%d %H:%M}.",
                )
                sent += 1
    return {"reminders": sent}


@job("privacy.retention_sweep", schedule="30 3 * * *")
def retention_sweep() -> dict[str, Any]:
    """Delete or anonymize data past its purpose's retention (see apps.privacy.retention)."""
    from apps.privacy.retention import sweep

    return {"total": sweep()["total"]}


@job("privacy.exports_cleanup", schedule="45 3 * * *")
def exports_cleanup() -> dict[str, Any]:
    """Delete export archives past their expiry."""
    from apps.privacy.models import DataSubjectRequest

    removed = 0
    for request in DataSubjectRequest.objects.filter(export_expires_at__lt=timezone.now()).exclude(
        export_name=""
    ):
        default_storage.delete(request.export_name)
        request.export_name = ""
        request.save(update_fields=["export_name", "updated_at"])
        removed += 1
    return {"removed": removed}


@job("privacy.unverified_cleanup", schedule="0 4 * * *")
def unverified_cleanup() -> dict[str, Any]:
    """Cancel public requests whose e-mail was never confirmed within 48 hours."""
    from apps.privacy.models import DataSubjectRequest

    cancelled = 0
    stale = DataSubjectRequest.objects.filter(
        status=DataSubjectRequest.Status.VERIFYING,
        created_at__lt=timezone.now() - timedelta(hours=48),
    )
    for request in stale:
        request.transition_to(DataSubjectRequest.Status.CANCELLED)
        cancelled += 1
    return {"cancelled": cancelled}
