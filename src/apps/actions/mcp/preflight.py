"""What Django's middleware does for ``/api`` and ``/mcp`` would otherwise skip.

A request to ``/mcp`` is routed by the ASGI dispatcher *before* Django, so none of the
middleware runs. Everything that matters for parity is repeated here, in one place:

* the validated client address (same trusted-proxy logic as the REST stack);
* a server-minted request id, echoed in the response and bound to the log context;
* a per-address request budget, before any authentication work;
* the organization named in the URL (``/mcp/<slug>``);
* response headers (``no-store``, ``nosniff``);
* the request-body cap lives one layer out, in ``config.asgi.BodyLimitMiddleware``.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from contextvars import ContextVar
from typing import Any

from django.conf import settings
from django.core.cache import cache

from apps.common.network import client_ip_bucket

client_ip_var: ContextVar[str | None] = ContextVar("mcp_client_ip", default=None)
org_slug_var: ContextVar[str | None] = ContextVar("mcp_org_slug", default=None)


class ScopeRequest:
    """Just enough of an ``HttpRequest`` for :func:`apps.common.network.client_ip`."""

    def __init__(self, scope: Mapping[str, Any]) -> None:
        client = scope.get("client")
        self.META = {"REMOTE_ADDR": client[0] if client else ""}
        self.headers = _CaseInsensitive(
            {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        )


class _CaseInsensitive(dict[str, str]):
    def get(self, key: str, default: Any = None) -> Any:
        return super().get(key.lower(), default)


def client_address(scope: Mapping[str, Any]) -> str | None:
    return client_ip_bucket(ScopeRequest(scope))  # type: ignore[arg-type]


def over_budget(address: str | None) -> bool:
    """Per-address requests per minute. Fails open, like every throttle in the stack."""
    limit = int(settings.MCP_RATE_PER_MINUTE_IP)
    if limit <= 0 or not address:
        return False
    key = f"mcp:ip:{address}:{int(time.time() // 60)}"
    try:
        cache.add(key, 0, 120)
        return int(cache.incr(key)) > limit
    except Exception:
        return False


def new_request_id() -> str:
    return str(uuid.uuid4())


SECURITY_HEADERS = (
    (b"cache-control", b"no-store"),
    (b"x-content-type-options", b"nosniff"),
)
