from __future__ import annotations

import os
from typing import Any

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

django_application = get_asgi_application()

from django.conf import settings  # noqa: E402  (needs settings configured)

from apps.common.asgi import BodyLimitMiddleware  # noqa: E402

inner: Any = django_application
if settings.MCP_ENABLED:
    # Imported only when enabled: with the flag off FastMCP is never loaded.
    from apps.actions.mcp.asgi import build_mcp_application

    inner = build_mcp_application(django_application)

# Django enforces DATA_UPLOAD_MAX_MEMORY_SIZE only when ``request.body`` is read; DRF streams
# the body instead and the ASGI handler spools it to disk first, so the cap lives here, in
# front of both Django and /mcp.
application = BodyLimitMiddleware(inner)
