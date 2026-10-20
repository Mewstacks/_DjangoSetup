from __future__ import annotations

import hashlib
import hmac
from typing import Any

from django.conf import settings
from django.db.models import Model

from apps.audit.models import AuditEvent
from apps.common.context import request_id_var
from apps.common.network import client_ip


def hash_ip(ip_address: str | None) -> str:
    if not ip_address or not settings.PRIVACY_HMAC_KEY:
        return ""
    return hmac.new(
        settings.PRIVACY_HMAC_KEY.encode(),
        f"audit-ip:{ip_address}".encode(),
        hashlib.sha256,
    ).hexdigest()


def record_event(
    *,
    action: str,
    actor: Any = None,
    organization: Any = None,
    target: Model | None = None,
    request: Any = None,
    success: bool = True,
    metadata: dict[str, object] | None = None,
) -> AuditEvent:
    request_ip = client_ip(request) if request is not None else None
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        organization=organization,
        action=action,
        target_type=target._meta.label_lower if target else "",
        target_id=str(target.pk) if target else "",
        request_id=request_id_var.get() or "",
        ip_hash=hash_ip(request_ip),
        success=success,
        metadata=metadata or {},
    )
