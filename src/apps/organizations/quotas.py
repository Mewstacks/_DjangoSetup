"""Per-organization ceilings, so one tenant cannot fill the database or the bucket for all.

Every limit is a setting (``QUOTA_*``); ``0`` disables it. They are *guard rails*, not plans:
a product that sells tiers replaces ``limit_for`` with a lookup of the organization's plan and
keeps every call site unchanged.
"""

from __future__ import annotations

from django.conf import settings
from django.db.models import Sum

from apps.common.exceptions import DomainError
from apps.organizations.models import Organization

SETTING_FOR = {
    "api_keys": "QUOTA_API_KEYS_PER_ORG",
    "webhook_endpoints": "QUOTA_WEBHOOK_ENDPOINTS_PER_ORG",
    "upload_files": "QUOTA_UPLOAD_FILES_PER_ORG",
    "upload_bytes": "QUOTA_UPLOAD_BYTES_PER_ORG",
}


class QuotaExceeded(DomainError):
    status = 403
    code = "quota_exceeded"


def limit_for(organization: Organization, kind: str) -> int:
    """The ceiling for ``kind``; the one function a billing integration overrides."""
    return int(getattr(settings, SETTING_FOR[kind]))


def enforce(organization: Organization, kind: str, *, used: int, adding: int = 1) -> None:
    limit = limit_for(organization, kind)
    if limit > 0 and used + adding > limit:
        raise QuotaExceeded(
            f"This organization reached its limit of {limit} for {kind.replace('_', ' ')}.",
            extra={"kind": kind, "limit": limit},
        )


def api_keys(organization: Organization) -> None:
    from apps.apikeys.models import ApiKey

    used = ApiKey.objects.filter(organization=organization, revoked_at__isnull=True).count()
    enforce(organization, "api_keys", used=used)


def webhook_endpoints(organization: Organization) -> None:
    from apps.webhooks.models import WebhookEndpoint

    enforce(
        organization,
        "webhook_endpoints",
        used=WebhookEndpoint.objects.filter(organization=organization).count(),
    )


def uploads(organization: Organization, *, size: int) -> None:
    from apps.uploads.models import UploadedFile

    rows = UploadedFile.objects.filter(organization=organization)
    enforce(organization, "upload_files", used=rows.count())
    enforce(
        organization,
        "upload_bytes",
        used=int(rows.aggregate(total=Sum("size"))["total"] or 0),
        adding=size,
    )
