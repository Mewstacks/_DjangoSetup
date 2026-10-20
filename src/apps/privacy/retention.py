"""Retention (LGPD art. 15 and 16): data is deleted or anonymized when its purpose ends.

Each classified model names a ``retention_field`` (the clock starts there) and a purpose whose
``retention_days`` says how long. Past that, the model's own ``on_erase`` rule applies - except
``keep`` (a legal duty) and rows of people under a legal hold, which are never touched. A
dry run reports counts and changes nothing.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import structlog
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.privacy.catalog import CATALOG
from apps.privacy.models import LegalHold, ProcessingPurpose

logger = structlog.get_logger("apps.privacy.retention")


def sweep(*, dry_run: bool = False) -> dict[str, Any]:
    now = timezone.now()
    held_users = set(
        LegalHold.objects.filter(released_at__isnull=True, subject__user__isnull=False).values_list(
            "subject__user_id", flat=True
        )
    )
    report: dict[str, Any] = {}
    purposes = {p.code: p for p in ProcessingPurpose.objects.all()}
    for item in sorted(CATALOG.values(), key=lambda c: c.label):
        if not item.personal or not item.retention_field or item.on_erase == "keep":
            continue
        purpose = purposes.get(item.purpose)
        if purpose is None:
            report[item.label] = {"skipped": f"purpose {item.purpose!r} does not exist"}
            continue
        cutoff = now - timedelta(days=purpose.retention_days)
        expired = item.model._default_manager.filter(**{f"{item.retention_field}__lt": cutoff})
        owner_field = _owner_field(item)
        if owner_field and held_users:
            expired = expired.exclude(**{f"{owner_field}__in": held_users})
        count = expired.count()
        if not count:
            continue
        outcome = {"expired": count, "action": item.on_erase, "dry_run": dry_run}
        if not dry_run:
            with transaction.atomic():
                if item.on_erase == "delete":
                    expired.delete()
                else:
                    expired.update(**item.anonymize)
        report[item.label] = outcome
    total = sum(v.get("expired", 0) for v in report.values())
    if total and not dry_run:
        record_event(action="privacy.retention_sweep", metadata={"rows": total})
    logger.info("retention_sweep", rows=total, dry_run=dry_run)
    return {"models": report, "total": total, "dry_run": dry_run}


def _owner_field(item: Any) -> str:
    """The foreign key to the account, found from the resolver's own lookup when it has one."""
    for name in ("user", "actor", "created_by", "requester"):
        if any(f.name == name for f in item.model._meta.get_fields()):
            return name
    return ""
