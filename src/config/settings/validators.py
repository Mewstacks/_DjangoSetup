"""Production configuration validators.

Kept apart from ``production.py`` so each rule can be unit-tested without booting a settings
module. Every function raises ``ImproperlyConfigured`` with a message that names the variable
to fix; none of them reads the environment itself.
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

# Values that show up in example files, docs and test settings. A real secret never contains them.
PLACEHOLDER_MARKERS = (
    "replace",
    "changeme",
    "change-me",
    "insecure",
    "example",
    "placeholder",
    "local-only",
    "test-",
    "secret",
    "password",
)
_BASE64URL = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")
# `require` encrypts but does not check who answered; a certificate-checking mode does.
VERIFYING_SSLMODES = {"verify-ca", "verify-full"}
SECURE_SSLMODES = VERIFYING_SSLMODES | {"require"}


def check_secret(name: str, value: str, *, min_length: int, min_distinct: int = 12) -> None:
    """Reject short, placeholder-looking or low-variety secrets."""
    if len(value) < min_length:
        raise ImproperlyConfigured(f"{name} must contain at least {min_length} random characters.")
    lowered = value.lower()
    for marker in PLACEHOLDER_MARKERS:
        if marker in lowered:
            raise ImproperlyConfigured(
                f"{name} looks like a placeholder (contains {marker!r}); generate a random value."
            )
    if len(set(value)) < min_distinct:
        raise ImproperlyConfigured(f"{name} has too little variety to be a random secret.")


def decode_key(key_id: str, encoded: str) -> bytes:
    """Strictly decode one base64url 32-byte key (``urlsafe_b64decode`` silently drops junk)."""
    if not isinstance(encoded, str) or not _BASE64URL.fullmatch(encoded):
        raise ImproperlyConfigured(f"Field encryption key {key_id!r} is not valid base64url.")
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ImproperlyConfigured(f"Field encryption key {key_id!r} is invalid.") from exc
    if len(decoded) != 32:
        raise ImproperlyConfigured(
            f"Field encryption key {key_id!r} must decode to exactly 32 bytes."
        )
    if len(set(decoded)) < 8:
        raise ImproperlyConfigured(f"Field encryption key {key_id!r} is not random.")
    return decoded


def check_key_ring(active_id: str, ring: Mapping[str, str]) -> None:
    if not ring or not active_id:
        raise ImproperlyConfigured("Production field encryption keys are required.")
    if active_id not in ring:
        raise ImproperlyConfigured(
            "The active field encryption key ID is missing from the key ring."
        )
    decoded = {key_id: decode_key(key_id, encoded) for key_id, encoded in ring.items()}
    if len(set(decoded.values())) != len(decoded):
        raise ImproperlyConfigured("Field encryption keys in the ring must all be different.")


def check_distinct_secrets(**secrets: str) -> None:
    """SECRET_KEY, the HMAC key and the field keys protect different things; never share one."""
    seen: dict[str, str] = {}
    for name, value in secrets.items():
        if value in seen:
            raise ImproperlyConfigured(f"{name} must differ from {seen[value]}.")
        seen[value] = name


def check_database(
    database: Mapping[str, Any],
    *,
    allow_insecure_transport: bool,
    allow_unverified_tls: bool = False,
) -> None:
    if database.get("ENGINE") != "django.db.backends.postgresql":
        raise ImproperlyConfigured("Production requires PostgreSQL.")
    mode = (database.get("OPTIONS") or {}).get("sslmode")
    if mode in VERIFYING_SSLMODES:
        return
    if mode == "require":
        if allow_unverified_tls or allow_insecure_transport:
            return
        raise ImproperlyConfigured(
            "sslmode=require encrypts the database connection but never checks the server "
            "certificate, so anyone on the path can impersonate it. Use sslmode=verify-full "
            "(with sslrootcert=system or your CA file). DB_ALLOW_UNVERIFIED_TLS=true records "
            "that you accept the risk."
        )
    if allow_insecure_transport:
        return
    raise ImproperlyConfigured(
        "Production database must use TLS: set sslmode to verify-full (or verify-ca). When "
        "Postgres is reachable only over a private network you control, "
        "DB_ALLOW_INSECURE_TRANSPORT=true records that decision."
    )


def check_redis_url(url: str, *, allow_insecure: bool) -> None:
    if not url:
        raise ImproperlyConfigured("Production requires REDIS_URL.")
    parsed = urlparse(url)
    if parsed.scheme == "rediss" or allow_insecure:
        return
    raise ImproperlyConfigured(
        "REDIS_URL must use rediss://: it carries sessions, lockout counters and throttles, and a "
        "password alone travels in clear. On a private network you control, "
        "REDIS_ALLOW_INSECURE=true records that decision."
    )


def check_origins(name: str, origins: Iterable[str]) -> None:
    for origin in origins:
        parsed = urlparse(origin)
        if origin in {"*", "null"} or "*" in origin:
            raise ImproperlyConfigured(f"{name} must not contain wildcards or 'null'.")
        if parsed.scheme != "https" or not parsed.hostname:
            raise ImproperlyConfigured(f"{name} entry {origin!r} must be an https:// origin.")


def check_hosts(hosts: Iterable[str]) -> None:
    hosts = list(hosts)
    if not hosts:
        raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS; there is no production default.")
    for host in hosts:
        if "*" in host:
            raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not contain wildcards.")
        if host in {"localhost", "127.0.0.1", "[::1]"}:
            raise ImproperlyConfigured(
                f"DJANGO_ALLOWED_HOSTS must not contain {host!r} in production."
            )


def check_proxy(*, proxy_ips: list[str], proxy_count: int, direct: bool) -> None:
    """Without this the client IP collapses to the proxy's address and every user shares one
    throttle and lockout bucket."""
    if proxy_ips or proxy_count > 0 or direct:
        return
    raise ImproperlyConfigured(
        "Declare how the app is reached: TRUSTED_PROXY_COUNT / TRUSTED_PROXY_IPS behind a "
        "reverse proxy or load balancer, or TRUSTED_PROXY_DIRECT=true when clients connect "
        "to the app directly."
    )


def check_temporal(
    *,
    enabled: bool,
    payload_encryption: bool,
    allow_plaintext: bool,
    tls: bool,
    api_key: str,
    allow_insecure: bool,
) -> None:
    """Whoever reaches the Temporal frontend can start any activity, so it must be authenticated.

    Sealed payloads are the application-level proof (nobody else holds the key ring); TLS or an
    API key keeps strangers off the wire. A private network you control is a legitimate answer,
    but it has to be written down: ``TEMPORAL_ALLOW_INSECURE=true``.
    """
    if not enabled:
        return
    if not payload_encryption or allow_plaintext:
        raise ImproperlyConfigured(
            "Production Temporal needs sealed payloads: TEMPORAL_PAYLOAD_ENCRYPTION=true and "
            "TEMPORAL_ALLOW_PLAINTEXT_PAYLOADS=false."
        )
    if not (tls or api_key or allow_insecure):
        raise ImproperlyConfigured(
            "Production Temporal must use TLS (TEMPORAL_TLS=true) or an API key; on a private "
            "network you control, TEMPORAL_ALLOW_INSECURE=true records that decision."
        )


def check_privacy_contacts(
    *, controller_name: str, dpo_email: str, dpo_contact_url: str, allow_undeclared: bool
) -> None:
    """The controller and a channel to the DPO are published by the transparency endpoint.

    LGPD art. 41 par. 1 asks for the DPO's identity and contact to be public, and small agents
    that are not required to name one still owe data subjects a channel (Res. CD/ANPD 18/2024).
    A product that launches with neither has nobody to answer an access request within 15 days.
    """
    if allow_undeclared:
        return
    if not controller_name.strip():
        raise ImproperlyConfigured(
            "Set PRIVACY_CONTROLLER_NAME (and PRIVACY_CONTROLLER_ID): the transparency endpoint "
            "publishes who is responsible for personal data. "
            "PRIVACY_ALLOW_UNDECLARED_CONTROLLER=true records that you decided otherwise."
        )
    if not (dpo_email.strip() or dpo_contact_url.strip()):
        raise ImproperlyConfigured(
            "Set DPO_EMAIL or DPO_CONTACT_URL: data subjects need a channel to the DPO, and the "
            "15-day reminders are sent there."
        )


def check_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path not in {"", "/"}:
        raise ImproperlyConfigured(
            "PUBLIC_URL must be the https origin of this service (https://app.example.com): "
            "e-mailed links (data exports, verification) are built from it."
        )


def check_email_backend(backend: str) -> None:
    if backend.endswith(("console.EmailBackend", "locmem.EmailBackend", "dummy.EmailBackend")):
        raise ImproperlyConfigured("Production needs a real EMAIL_BACKEND.")


def check_hsts(seconds: int) -> None:
    if seconds < 86_400:
        raise ImproperlyConfigured("SECURE_HSTS_SECONDS must be at least one day in production.")
