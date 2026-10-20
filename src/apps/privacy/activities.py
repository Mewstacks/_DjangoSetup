"""Activities of the privacy flows: thin wrappers over ``apps.privacy.services``."""

from __future__ import annotations

from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from apps.common.exceptions import DomainError
from apps.flows.declare import activity as register_activity
from apps.privacy.workflows import STEP_ACTIVITY, StepCall


def dsar_step_impl(request_id: str, step: str, now: str | None = None) -> dict[str, Any]:
    from datetime import datetime

    from apps.privacy import services
    from apps.privacy.models import DataSubjectRequest

    request = DataSubjectRequest.objects.get(pk=request_id)
    if step == "execute":
        return services.execute_request(request)
    if step == "remind":
        clock = datetime.fromisoformat(now) if now else None
        return {"sent": services.send_reminders(request, now=clock)}
    request.refresh_from_db()
    return {"state": request.status}


@register_activity
@activity.defn(name=STEP_ACTIVITY)
def dsar_step(call: StepCall) -> dict[str, Any]:
    try:
        return dsar_step_impl(call.request_id, call.step, call.now)
    except DomainError as error:
        raise ApplicationError(
            f"{error.code}: {error.detail}", type=type(error).__name__, non_retryable=True
        ) from error
