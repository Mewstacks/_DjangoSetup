from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

django_application = get_asgi_application()

from apps.common.asgi import BodyLimitMiddleware  # noqa: E402  (needs settings loaded)

# Django enforces DATA_UPLOAD_MAX_MEMORY_SIZE only when ``request.body`` is read; DRF streams
# the body instead and the ASGI handler spools it to disk first, so the cap has to live here.
application = BodyLimitMiddleware(django_application)
