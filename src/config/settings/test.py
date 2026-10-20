from config.settings.base import *
from config.settings.env import env_bool

SECRET_KEY = "test-only-secret-key-not-used-outside-the-test-suite"
DEBUG = False
if not env_bool("TEST_USE_EXTERNAL_SERVICES", False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-cache",
        }
    }
    AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
FIELD_ENCRYPTION_ACTIVE_KEY_ID = "test-v1"
FIELD_ENCRYPTION_KEYS = {
    "test-v1": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
}
PRIVACY_HMAC_KEY = "test-independent-hmac-key"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
HEALTH_READINESS_CACHE_SECONDS = 0
