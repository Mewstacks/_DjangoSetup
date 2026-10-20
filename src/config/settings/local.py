from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from config.settings.base import *  # noqa: E402

DEBUG = True
ADMIN_ENABLED = True
API_DOCS_ENABLED = True
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"
