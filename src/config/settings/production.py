from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from config.settings import validators
from config.settings.base import *
from config.settings.env import env_bool, env_int, env_list, env_str

DEBUG = False
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# No default hosts in production: the local defaults in base.py would pass a lazy check.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
validators.check_hosts(ALLOWED_HOSTS)
validators.check_public_url(PUBLIC_URL)
validators.check_privacy_contacts(
    controller_name=PRIVACY_CONTROLLER_NAME,
    dpo_email=DPO_EMAIL,
    dpo_contact_url=DPO_CONTACT_URL,
    allow_undeclared=env_bool("PRIVACY_ALLOW_UNDECLARED_CONTROLLER", False),
)
validators.check_origins("DJANGO_CSRF_TRUSTED_ORIGINS", CSRF_TRUSTED_ORIGINS)
validators.check_origins("DJANGO_CORS_ALLOWED_ORIGINS", CORS_ALLOWED_ORIGINS)

validators.check_secret("DJANGO_SECRET_KEY", SECRET_KEY, min_length=50)
validators.check_secret("PRIVACY_HMAC_KEY", PRIVACY_HMAC_KEY, min_length=32)
validators.check_secret("AUDIT_HMAC_KEY", AUDIT_HMAC_KEY, min_length=32)
for _index, _old_key in enumerate(PRIVACY_HMAC_KEYS_PREVIOUS):
    validators.check_secret(f"PRIVACY_HMAC_KEYS_PREVIOUS[{_index}]", _old_key, min_length=32)
for _index, _old_key in enumerate(SECRET_KEY_FALLBACKS):
    validators.check_secret(f"DJANGO_SECRET_KEY_FALLBACKS[{_index}]", _old_key, min_length=50)
validators.check_key_ring(FIELD_ENCRYPTION_ACTIVE_KEY_ID, FIELD_ENCRYPTION_KEYS)
validators.check_distinct_secrets(
    DJANGO_SECRET_KEY=SECRET_KEY,
    PRIVACY_HMAC_KEY=PRIVACY_HMAC_KEY,
    AUDIT_HMAC_KEY=AUDIT_HMAC_KEY,
    **{
        f"FIELD_ENCRYPTION_KEYS[{key_id}]": value for key_id, value in FIELD_ENCRYPTION_KEYS.items()
    },
)

validators.check_database(
    DATABASES["default"],
    allow_insecure_transport=env_bool("DB_ALLOW_INSECURE_TRANSPORT", False),
    allow_unverified_tls=env_bool("DB_ALLOW_UNVERIFIED_TLS", False),
)
validators.check_redis_url(redis_url, allow_insecure=env_bool("REDIS_ALLOW_INSECURE", False))
validators.check_temporal(
    enabled=TEMPORAL_ENABLED,
    payload_encryption=TEMPORAL_PAYLOAD_ENCRYPTION,
    allow_plaintext=TEMPORAL_ALLOW_PLAINTEXT_PAYLOADS,
    tls=TEMPORAL_TLS,
    api_key=TEMPORAL_API_KEY,
    allow_insecure=env_bool("TEMPORAL_ALLOW_INSECURE", False),
)
validators.check_proxy(
    proxy_ips=TRUSTED_PROXY_IPS,
    proxy_count=TRUSTED_PROXY_COUNT,
    direct=env_bool("TRUSTED_PROXY_DIRECT", False),
)
for _entry in TRUSTED_PROXY_IPS:
    # A typo'd CIDR used to be dropped silently, trusting fewer proxies than intended.
    from apps.common.network import parse_trusted_networks

    try:
        parse_trusted_networks([_entry])
    except ValueError as exc:
        raise ImproperlyConfigured(f"TRUSTED_PROXY_IPS entry {_entry!r} is not a CIDR.") from exc

# The admin and the interactive docs are off unless asked for, and asking is not enough on
# its own: the admin additionally needs an IP allowlist, the docs need an admin session.
ADMIN_ENABLED = env_bool("ADMIN_ENABLED", False)
API_DOCS_ENABLED = env_bool("API_DOCS_ENABLED", False)
if ADMIN_ENABLED and not ADMIN_ALLOWED_IPS:
    raise ImproperlyConfigured("ADMIN_ENABLED in production requires ADMIN_ALLOWED_IPS.")
# Owners and administrators manage people, keys and webhooks: they need a second factor.
ORG_PRIVILEGED_MFA_REQUIRED = env_bool("ORG_PRIVILEGED_MFA_REQUIRED", True)
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = env_bool("DB_PGBOUNCER", False)

if NETGUARD_ALLOW_PRIVATE:
    raise ImproperlyConfigured("NETGUARD_ALLOW_PRIVATE must be off in production (SSRF guard).")
if env_str("LOG_LEVEL", "INFO").upper() == "DEBUG":
    raise ImproperlyConfigured("LOG_LEVEL=DEBUG is not allowed in production.")

SECURE_SSL_REDIRECT = True
# Probes come from the platform without TLS or the forwarded header; redirecting them would
# make every health check fail. Everything else is redirected.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/"]
if TRUSTED_PROXY_IPS or TRUSTED_PROXY_COUNT > 0:
    # Only trust the forwarded scheme when the deployment declared a proxy in front of it.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
for cookie_name, samesite in (
    ("SESSION_COOKIE_SAMESITE", SESSION_COOKIE_SAMESITE),
    ("CSRF_COOKIE_SAMESITE", CSRF_COOKIE_SAMESITE),
):
    if samesite not in {"Lax", "Strict", "None"}:
        raise ImproperlyConfigured(f"{cookie_name} must be 'Lax', 'Strict', or 'None'.")
# includeSubdomains and preload are commitments about the whole parent domain, so they are
# opt-in: turning them on by default would break sibling subdomains on a shared domain.
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31_536_000)
validators.check_hsts(SECURE_HSTS_SECONDS)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
# `check --deploy` nags about the two opt-ins above. They are decisions about the whole parent
# domain, not defaults to flip, so the nag is silenced until the operator turns them on.
SILENCED_SYSTEM_CHECKS = [
    *SILENCED_SYSTEM_CHECKS,
    *([] if SECURE_HSTS_INCLUDE_SUBDOMAINS else ["security.W005"]),
    *([] if SECURE_HSTS_PRELOAD else ["security.W021"]),
]

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = ["rest_framework.renderers.JSONRenderer"]

STORAGES["staticfiles"] = {
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
}

# S3_* is the documented spelling; BUCKET_NAME / AWS_MEDIA_BUCKET / AWS_REGION /
# AWS_ENDPOINT_URL_S3 remain accepted so existing deployments keep booting.
media_bucket = env_str("S3_BUCKET") or env_str("BUCKET_NAME") or env_str("AWS_MEDIA_BUCKET")
# Without a bucket, media would land on the container's ephemeral disk and vanish on restart.
if env_bool("OBJECT_STORAGE_REQUIRED", True) and not media_bucket:
    raise ImproperlyConfigured(
        "Production object storage is required: set S3_BUCKET (or OBJECT_STORAGE_REQUIRED=false "
        "when /app/media is a persistent volume)."
    )
if media_bucket:
    object_parameters = {}
    media_kms_key = env_str("AWS_MEDIA_KMS_KEY_ID")
    if media_kms_key:
        object_parameters = {
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": media_kms_key,
        }
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": media_bucket,
            "region_name": env_str("S3_REGION") or env_str("AWS_REGION") or None,
            "endpoint_url": env_str("S3_ENDPOINT_URL") or env_str("AWS_ENDPOINT_URL_S3") or None,
            "addressing_style": env_str("S3_ADDRESSING_STYLE", "auto"),
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 300,
            "file_overwrite": False,
            "object_parameters": object_parameters,
        },
    }

email_backend = env_str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
validators.check_email_backend(email_backend)
MAILERS = {
    "default": {
        "BACKEND": email_backend,
        "OPTIONS": {
            "host": env_str("EMAIL_HOST", "localhost"),
            "port": env_int("EMAIL_PORT", 587),
            "use_tls": env_bool("EMAIL_USE_TLS", True),
            "username": env_str("EMAIL_HOST_USER"),
            "password": env_str("EMAIL_HOST_PASSWORD"),
        },
    }
}

sentry_enabled = env_bool("SENTRY_ENABLED", True)
sentry_dsn = env_str("SENTRY_DSN")
if sentry_enabled and not sentry_dsn:
    raise ImproperlyConfigured(
        "SENTRY_DSN is required in production; set SENTRY_ENABLED=false only intentionally."
    )
if sentry_enabled:
    import sentry_sdk

    from apps.common.sentry import before_send, before_send_transaction, traces_sampler

    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=env_str("SENTRY_ENVIRONMENT", "production"),
        release=env_str("SENTRY_RELEASE") or None,
        send_default_pii=False,
        before_send=before_send,
        before_send_transaction=before_send_transaction,
        traces_sampler=traces_sampler,
        profiles_sample_rate=0.0,
        max_breadcrumbs=50,
        max_request_body_size="never",
        include_local_variables=False,
        include_source_context=False,
    )
