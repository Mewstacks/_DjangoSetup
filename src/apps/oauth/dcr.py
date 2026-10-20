"""Who may register an OAuth client dynamically (RFC 7591)."""

from __future__ import annotations

import time
from typing import Any

from django.conf import settings
from django.core.cache import cache
from oauth2_provider.dcr import IsAuthenticatedDCRPermission

from apps.common.network import client_ip_bucket

PER_HOUR = 20


class DCRPermission:
    """Signed-in users always; anonymous callers only when ``OAUTH_DCR_ANONYMOUS`` is on.

    MCP clients register themselves before any user is involved, which is why the anonymous
    mode exists. It is throttled per client address, and a registered client still gets no
    token until a user consents to it on the authorize screen, so a flood of registrations
    costs rows, not access.
    """

    def has_permission(self, request: Any) -> bool:
        if IsAuthenticatedDCRPermission().has_permission(request):
            return True
        if not settings.OAUTH_DCR_ANONYMOUS:
            return False
        key = f"oauth:dcr:{client_ip_bucket(request)}:{int(time.time() // 3600)}"
        try:
            cache.add(key, 0, 7200)
            return int(cache.incr(key)) <= PER_HOUR
        except Exception:
            return False
