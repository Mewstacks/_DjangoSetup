from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from config.settings.base import *  # noqa: E402

DEBUG = True
ADMIN_ENABLED = True
API_DOCS_ENABLED = True
HEALTH_DETAIL_PUBLIC = True
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"

# Swagger UI and the DRF browsable API load inline styles and CDN assets.
from django.utils.csp import CSP  # noqa: E402

SECURE_CSP = {
    **SECURE_CSP,
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE, "https://cdn.jsdelivr.net"],
    "script-src": [CSP.SELF, CSP.UNSAFE_INLINE, "https://cdn.jsdelivr.net"],
    "img-src": [CSP.SELF, "data:", "https://cdn.jsdelivr.net"],
}
