from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.utils.csp import CSP

from config.settings.env import env_bool, env_int, env_json, env_list, env_str

PROJECT_ROOT = Path(__file__).resolve().parents[3]

SECRET_KEY = env_str(
    "DJANGO_SECRET_KEY",
    "insecure-local-only-key-change-before-production",
)
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ("localhost", "127.0.0.1"))
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "axes",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
]
LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.organizations",
    "apps.audit",
    "apps.privacy",
]
INSTALLED_APPS = [*DJANGO_APPS, *THIRD_PARTY_APPS, *LOCAL_APPS]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.common.middleware.RequestContextMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.organizations.middleware.OrganizationContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [PROJECT_ROOT / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csp",
            ],
        },
    },
]

database_url = env_str("DATABASE_URL")
db_engine = env_str("DB_ENGINE", "postgresql" if database_url else "sqlite")
if database_url:
    parsed_database_url = urlparse(database_url)
    if parsed_database_url.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("DATABASE_URL must use the postgres or postgresql scheme.")
    query_options = {key: values[-1] for key, values in parse_qs(parsed_database_url.query).items()}
    if env_bool("DB_SSL_REQUIRE", False):
        query_options.setdefault("sslmode", "require")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed_database_url.path.lstrip("/")),
            "USER": unquote(parsed_database_url.username or ""),
            "PASSWORD": unquote(parsed_database_url.password or ""),
            "HOST": parsed_database_url.hostname or "",
            "PORT": parsed_database_url.port or 5432,
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": query_options,
        }
    }
elif db_engine == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": PROJECT_ROOT / "db.sqlite3",
        }
    }
elif db_engine == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("DB_NAME", "saas"),
            "USER": env_str("DB_USER", "saas"),
            "PASSWORD": env_str("DB_PASSWORD"),
            "HOST": env_str("DB_HOST", "127.0.0.1"),
            "PORT": env_str("DB_PORT", "5432"),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                **({"sslmode": "require"} if env_bool("DB_SSL_REQUIRE", False) else {}),
            },
        }
    }
else:
    raise RuntimeError("DB_ENGINE must be either 'sqlite' or 'postgresql'.")

redis_url = env_str("REDIS_URL")
FLY_APP_NAME = env_str("FLY_APP_NAME")
deployment_name = env_str("APP_NAME") or FLY_APP_NAME or "saas"

# Host-agnostic client-IP resolution (see apps.common.network.client_ip). Set whichever
# matches the deployment; both default to trusting only the direct peer.
TRUSTED_PROXY_IPS = env_list("TRUSTED_PROXY_IPS")
TRUSTED_PROXY_COUNT = env_int("TRUSTED_PROXY_COUNT", 0)
if redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": redis_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 3,
                "SOCKET_TIMEOUT": 3,
                "IGNORE_EXCEPTIONS": False,
            },
            "KEY_PREFIX": env_str("CACHE_KEY_PREFIX", deployment_name),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "saas-local-cache",
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = PROJECT_ROOT / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = PROJECT_ROOT / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# Fail safe: the admin and the interactive API docs are off unless a settings module or
# the environment opts in. local.py turns them on for development; production keeps them
# off. A deployment that forgets to use production.py therefore does not expose them.
ADMIN_ENABLED = env_bool("ADMIN_ENABLED", False)
API_DOCS_ENABLED = env_bool("API_DOCS_ENABLED", False)

# The readiness probe stays unauthenticated and unthrottled so that a cache outage can
# never turn a "degraded" answer into a 500. Memoising the result per worker keeps the
# endpoint from being a cheap way to hammer the database instead.
HEALTH_READINESS_CACHE_SECONDS = env_int("HEALTH_READINESS_CACHE_SECONDS", 5)

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE_SECONDS", 43_200)
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_HTTPONLY = True
# Secure by default; local.py relaxes this for plain-HTTP development and production.py
# pins it True. A new settings module thus cannot silently ship insecure cookies.
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
# "Lax" assumes the browser client is same-site. A SPA served from a different site
# needs "None" (which production enforces alongside Secure) or the session cookie is
# never sent with the cross-site XHR.
SESSION_COOKIE_SAMESITE = env_str("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = env_str("CSRF_COOKIE_SAMESITE", "Lax")

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "base-uri": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "font-src": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "img-src": [CSP.SELF, "data:", "https:"],
    "object-src": [CSP.NONE],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
}

CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "x-csrftoken",
    "x-organization-id",
    "x-request-id",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultPagination",
    "PAGE_SIZE": 50,
    # Throttle buckets are keyed by the validated edge IP, never by a forwarded header.
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.common.throttling.IPAnonRateThrottle",
        "apps.common.throttling.IPUserRateThrottle",
    ],
    # Defence in depth: anything that still uses DRF's own get_ident must not read
    # X-Forwarded-For, which is fully caller-controlled.
    "NUM_PROXIES": 0,
    "DEFAULT_THROTTLE_RATES": {
        "anon": env_str("API_THROTTLE_ANON", "30/minute"),
        "user": env_str("API_THROTTLE_USER", "300/minute"),
        "privacy": env_str("API_THROTTLE_PRIVACY", "10/hour"),
        "organization_create": env_str("API_THROTTLE_ORGANIZATION_CREATE", "10/day"),
        "login": env_str("API_THROTTLE_LOGIN", "10/minute"),
    },
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SaaS Backend API",
    "DESCRIPTION": "Versioned API for the reusable SaaS backend.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "no-reply@localhost")
SERVER_EMAIL = env_str("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("DATA_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = env_int("FILE_UPLOAD_MAX_MEMORY_SIZE", 2_621_440)
# Cap the shape of a request, not just its size: bound the number of POST fields and
# uploaded files so a single request cannot exhaust CPU/memory building huge structures.
DATA_UPLOAD_MAX_NUMBER_FIELDS = env_int("DATA_UPLOAD_MAX_NUMBER_FIELDS", 1_000)
DATA_UPLOAD_MAX_NUMBER_FILES = env_int("DATA_UPLOAD_MAX_NUMBER_FILES", 100)
FILE_UPLOAD_PERMISSIONS = 0o640

FIELD_ENCRYPTION_ACTIVE_KEY_ID = env_str("FIELD_ENCRYPTION_ACTIVE_KEY_ID")
FIELD_ENCRYPTION_KEYS = env_json("FIELD_ENCRYPTION_KEYS", {})
PRIVACY_HMAC_KEY = env_str("PRIVACY_HMAC_KEY")
PRIVACY_REQUEST_TARGET_DAYS = env_int("PRIVACY_REQUEST_TARGET_DAYS", 15)

AXES_ENABLED = True
AXES_CLIENT_IP_CALLABLE = "apps.common.network.client_ip"
AXES_FAILURE_LIMIT = env_int("AXES_FAILURE_LIMIT", 5)
AXES_COOLOFF_TIME = timedelta(minutes=env_int("AXES_COOLOFF_MINUTES", 30))
AXES_USE_ATTEMPT_EXPIRATION = True
AXES_RESET_ON_SUCCESS = True
# (username, ip_address) alone never stops a distributed brute force against one
# account. Adding the username-only group closes that, at the cost of letting a third
# party lock somebody else out on purpose, so it stays an explicit deployment choice.
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
if env_bool("AXES_LOCKOUT_BY_USERNAME", False):
    AXES_LOCKOUT_PARAMETERS.append(["username"])
AXES_HANDLER = "axes.handlers.cache.AxesCacheHandler"
AXES_CACHE = "default"
AXES_USERNAME_FORM_FIELD = "email"
AXES_USERNAME_CALLABLE = "apps.accounts.security.axes_username"
AXES_SENSITIVE_PARAMETERS = ["password"]
AXES_HTTP_RESPONSE_CODE = 429
AXES_ENABLE_RETRY_AFTER_HEADER = True
AXES_LOCKOUT_CALLABLE = "apps.accounts.security.axes_lockout_response"
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", redis_url or "memory://")
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", redis_url or "cache+memory://")
CELERY_TASK_DEFAULT_QUEUE = env_str("CELERY_QUEUE_NAME", f"{deployment_name}-default")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TRACK_STARTED = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SOFT_TIME_LIMIT = env_int("CELERY_TASK_SOFT_TIME_LIMIT_SECONDS", 270)
CELERY_TASK_TIME_LIMIT = env_int("CELERY_TASK_TIME_LIMIT_SECONDS", 300)
CELERY_WORKER_MAX_TASKS_PER_CHILD = env_int("CELERY_WORKER_MAX_TASKS_PER_CHILD", 500)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_context": {"()": "apps.common.logging.RequestContextFilter"},
        "redact": {"()": "apps.common.logging.RedactSecretsFilter"},
    },
    "formatters": {
        "json": {"()": "apps.common.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_context", "redact"],
            "formatter": "json",
        }
    },
    "root": {"handlers": ["console"], "level": env_str("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
