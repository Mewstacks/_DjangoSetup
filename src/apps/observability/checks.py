"""``manage.py doctor``: one place that answers "is this deployment sound?".

Each check returns a status - ``ok``, ``info`` (informational), ``warn`` (works, but you would
want to fix it) or ``fail`` (broken or unsafe) - and a sentence. ``--strict`` turns warnings
into a failing exit code, which is what a deploy pipeline wants after the first rollout.

The checks read configuration and probe dependencies; none writes anything except a throwaway
cache key. Secrets are never printed.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

OK, INFO, WARN, FAIL = "ok", "info", "warn", "fail"


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def check_database() -> Check:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception as error:
        return Check("database", FAIL, f"cannot query: {type(error).__name__}")
    if pending:
        return Check("database", FAIL, f"{len(pending)} migration(s) not applied; run migrate")
    return Check("database", OK, f"{connection.vendor}, migrations applied")


def check_cache() -> Check:
    try:
        cache.set("doctor:probe", "1", 10)
        if cache.get("doctor:probe") != "1":
            return Check("cache", FAIL, "wrote a key and could not read it back")
    except Exception as error:
        return Check("cache", FAIL, f"unreachable: {type(error).__name__}")
    backend = str(settings.CACHES["default"]["BACKEND"]).rsplit(".", 1)[-1]
    if "LocMem" in backend and not settings.DEBUG:
        return Check(
            "cache", WARN, "per-process memory: throttles and lockout are not shared by workers"
        )
    return Check("cache", OK, backend)


def check_encryption() -> Check:
    from apps.common.encryption import decrypt_text, encrypt_text

    try:
        sample = encrypt_text("doctor", associated_data=b"doctor")
        if decrypt_text(sample, associated_data=b"doctor") != "doctor":
            return Check("encryption", FAIL, "round trip returned different text")
    except Exception as error:
        return Check("encryption", FAIL, f"key ring unusable: {type(error).__name__}")
    ring = len(settings.FIELD_ENCRYPTION_KEYS)
    return Check(
        "encryption", OK, f"active key {settings.FIELD_ENCRYPTION_ACTIVE_KEY_ID!r}, ring of {ring}"
    )


def check_debug() -> Check:
    if settings.DEBUG:
        return Check("debug", WARN, "DEBUG is on (fine locally, never in production)")
    return Check("debug", OK, "off")


def check_proxy() -> Check:
    if settings.TRUSTED_PROXY_IPS or settings.TRUSTED_PROXY_COUNT:
        return Check("client ip", OK, "behind a declared proxy")
    return Check(
        "client ip", WARN, "no proxy declared: every client is the direct peer (fine without one)"
    )


def check_admin() -> Check:
    if not settings.ADMIN_ENABLED:
        return Check("admin", OK, "disabled")
    if not settings.ADMIN_ALLOWED_IPS:
        return Check("admin", WARN, "enabled without ADMIN_ALLOWED_IPS (open to every address)")
    return Check("admin", OK, f"enabled for {len(settings.ADMIN_ALLOWED_IPS)} network(s)")


def check_https() -> Check:
    if settings.DEBUG:
        return Check("https", INFO, "development settings")
    problems = [
        name
        for name in ("SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SECURE_SSL_REDIRECT")
        if not getattr(settings, name, False)
    ]
    if problems:
        return Check("https", FAIL, f"not enforced: {', '.join(problems)}")
    return Check("https", OK, f"HSTS {settings.SECURE_HSTS_SECONDS}s, secure cookies, redirect")


def check_email() -> Check:
    backend = str(settings.MAILERS["default"]["BACKEND"])
    if backend.endswith(("console.EmailBackend", "locmem.EmailBackend")):
        return Check(
            "email",
            WARN if not settings.DEBUG else INFO,
            f"{backend.rsplit('.', 1)[-1]}: nothing is sent",
        )
    return Check("email", OK, backend.rsplit(".", 1)[-1])


def check_flows() -> Check:
    from apps.flows.declare import FLOWS

    if not settings.TEMPORAL_ENABLED:
        non_portable = sorted(n for n, s in FLOWS.items() if not s.portable and s.workflow)
        if non_portable and not settings.DEBUG:
            return Check(
                "flows",
                WARN,
                "local engine in production; these flows need Temporal: "
                + ", ".join(non_portable[:5]),
            )
        return Check("flows", INFO, "Temporal off: flows run inline on the local engine")
    try:
        from temporalio.api.workflowservice.v1 import GetSystemInfoRequest

        from apps.flows.runner import runner

        async def probe() -> str:
            client = await runner.client()
            await client.workflow_service.get_system_info(GetSystemInfoRequest())
            return str(settings.TEMPORAL_NAMESPACE)

        namespace = runner.run(probe, timeout=10)
    except Exception as error:
        return Check(
            "flows",
            FAIL,
            f"Temporal unreachable at {settings.TEMPORAL_ADDRESS}: {type(error).__name__}",
        )
    beat = cache.get("flows:worker:heartbeat")
    if beat is None:
        return Check(
            "flows", WARN, f"connected (namespace {namespace}) but no worker heartbeat seen"
        )
    age = time.time() - float(beat)
    if age > 90:
        return Check("flows", WARN, f"connected; worker heartbeat is {int(age)}s old")
    return Check("flows", OK, f"connected (namespace {namespace}), worker alive {int(age)}s ago")


def check_mcp() -> Check:
    if not settings.MCP_ENABLED:
        return Check("mcp", INFO, "disabled")
    if not settings.MCP_PUBLIC_URL:
        return Check("mcp", WARN, "enabled but MCP_PUBLIC_URL is empty (OAuth metadata needs it)")
    return Check("mcp", OK, f"{settings.MCP_PUBLIC_URL.rstrip('/')}{settings.MCP_PATH}")


def check_audit_chain() -> Check:
    from apps.audit.integrity import verify_all

    try:
        reports = verify_all()
    except Exception as error:
        return Check("audit chain", FAIL, f"cannot verify: {type(error).__name__}")
    broken = [r.chain_key for r in reports if not r.ok]
    if broken:
        return Check("audit chain", FAIL, f"tampering or gaps in: {', '.join(broken[:5])}")
    return Check(
        "audit chain", OK, f"{sum(r.checked for r in reports)} events in {len(reports)} chain(s)"
    )


def check_audit_privileges() -> Check:
    """On PostgreSQL the trail is only tamper-resistant if the runtime is not its owner."""
    if connection.vendor != "postgresql":
        return Check("audit privileges", INFO, "SQLite: no trigger or role separation")
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_userbyid(c.relowner) = current_user, "
                "has_table_privilege(current_user, c.oid, 'UPDATE'), "
                "has_table_privilege(current_user, c.oid, 'DELETE'), "
                "has_table_privilege(current_user, c.oid, 'TRUNCATE') "
                "FROM pg_class c WHERE c.oid = 'audit_auditevent'::regclass"
            )
            owns, can_update, can_delete, can_truncate = cursor.fetchone()
    except Exception as error:
        return Check("audit privileges", WARN, f"cannot inspect: {type(error).__name__}")
    if owns or can_update or can_delete or can_truncate:
        return Check(
            "audit privileges",
            WARN,
            "the runtime role can rewrite the audit trail; connect as a role that does not own "
            "the schema (AUDIT_RUNTIME_ROLE, see the hardening guide)",
        )
    return Check("audit privileges", OK, "the runtime role can append and read, nothing else")


def check_privacy() -> Check:
    """Is the LGPD plumbing configured, not just installed?"""
    from apps.privacy.models import PrivacyNotice, ProcessingPurpose

    problems = []
    if not settings.PRIVACY_CONTROLLER_NAME:
        problems.append("PRIVACY_CONTROLLER_NAME is empty")
    if not (settings.DPO_EMAIL or settings.DPO_CONTACT_URL):
        problems.append("no DPO channel (DPO_EMAIL or DPO_CONTACT_URL)")
    try:
        if not ProcessingPurpose.objects.filter(active=True).exists():
            problems.append("no processing purposes (run manage.py privacy_seed)")
        if not PrivacyNotice.objects.filter(active=True).exists():
            problems.append("no active privacy notice")
    except Exception as error:
        return Check("privacy", FAIL, f"cannot query: {type(error).__name__}")
    if problems:
        return Check("privacy", INFO if settings.DEBUG else WARN, "; ".join(problems))
    return Check("privacy", OK, "controller, DPO channel, purposes and notice are set")


def check_telemetry() -> Check:
    if not settings.OTEL_ENABLED:
        return Check("telemetry", INFO, "OpenTelemetry off")
    return Check("telemetry", OK, f"OpenTelemetry on, service {settings.OTEL_SERVICE_NAME!r}")


ALL: list[Callable[[], Check]] = [
    check_database,
    check_cache,
    check_encryption,
    check_debug,
    check_https,
    check_proxy,
    check_admin,
    check_email,
    check_flows,
    check_mcp,
    check_audit_chain,
    check_audit_privileges,
    check_privacy,
    check_telemetry,
]


def run_all() -> list[Check]:
    return [check() for check in ALL]
