"""Starting the flow for a request, and the entry points used by the API and the sweep job."""

from __future__ import annotations

import structlog
from django.db import transaction
from django.utils import timezone

from apps.flows.models import FlowRun
from apps.privacy.models import DataSubjectRequest

logger = structlog.get_logger("apps.privacy")


def workflow_id(request: DataSubjectRequest) -> str:
    return f"dsar:{request.pk}"


def start_dsar(request: DataSubjectRequest) -> bool:
    """Start the DSAR flow once. Failing to start never fails the caller: the sweep retries."""
    from apps.flows.engine import get_engine

    if FlowRun.objects.filter(workflow_id=workflow_id(request)).exists():
        return False
    try:
        get_engine().start(
            "privacy.dsar", {"request_id": str(request.pk)}, workflow_id=workflow_id(request)
        )
    except Exception:
        logger.exception("dsar_start_failed", request_id=str(request.pk))
        return False
    return True


def start_after_commit(request: DataSubjectRequest) -> None:
    """Inside a transaction the flow must not start before the request is committed."""
    transaction.on_commit(lambda: start_dsar(request))


def mark_verified(request: DataSubjectRequest) -> None:
    if request.identity_verified_at is None:
        request.identity_verified_at = timezone.now()
        request.save(update_fields=["identity_verified_at", "updated_at"])
