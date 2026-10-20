"""Housekeeping every deployment needs. Cron-scheduled in UTC; each is idempotent.

With Temporal on they run as Schedules (``manage.py flows_sync``). With it off, point cron or a
Kubernetes CronJob at ``manage.py run_job <name>``; ``manage.py run_job --due`` is a single
entry for "run whatever is due now" if you prefer one crontab line.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from apps.flows.declare import job


@job("maintenance.close_idle_runs", schedule="*/10 * * * *")
def close_idle_runs() -> dict[str, Any]:
    """Close MCP working sessions that have been idle past the gap."""
    from apps.actions.journal import close_idle_runs as close

    return {"closed": close()}


@job("maintenance.purge_journal", schedule="40 4 * * *")
def purge_journal() -> dict[str, Any]:
    """Delete change-journal rows past their retention (they hold business data)."""
    from apps.actions.journal import purge_journal as purge

    return {"deleted": purge()}


@job("maintenance.prune_idempotency", schedule="20 4 * * *")
def prune_idempotency() -> dict[str, Any]:
    """Drop idempotency keys older than a day: a retry that late is a new request."""
    from apps.actions.models import IdempotencyRecord

    deleted, _ = IdempotencyRecord.objects.filter(
        created_at__lt=timezone.now() - timedelta(hours=24)
    ).delete()
    return {"deleted": deleted}


@job("maintenance.clear_sessions", schedule="30 4 * * *")
def clear_sessions() -> dict[str, Any]:
    """Delete expired Django sessions."""
    call_command("clearsessions")
    return {}


@job("maintenance.prune_flow_runs", schedule="50 4 * * *")
def prune_flow_runs() -> dict[str, Any]:
    """Delete finished flow-run records older than 90 days."""
    from apps.flows.models import FlowRun

    deleted, _ = FlowRun.objects.filter(
        finished_at__lt=timezone.now() - timedelta(days=90)
    ).delete()
    return {"deleted": deleted}


if settings.OAUTH_ENABLED:

    @job("maintenance.clear_oauth_tokens", schedule="10 5 * * *")
    def clear_oauth_tokens() -> dict[str, Any]:
        """Remove expired OAuth access/refresh tokens and grants."""
        call_command("cleartokens")
        return {}
