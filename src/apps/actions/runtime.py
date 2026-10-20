"""The one place an action is authorised, throttled, run, recorded and reported.

Every channel - REST, MCP, Temporal, CLI - calls :func:`invoke`. Keeping the whole pipeline
in one function is the point: a rule added here (a new check, a new audit field) applies to
every way of reaching an action at once, and none of them can forget it.

Order of effects::

    channel -> scope -> role -> rate -> validate -> [ transaction:
        idempotency claim -> run -> audit (success) -> store response ] -> log

A *denial* is audited outside the transaction so it survives a rollback; a success is audited
inside it so it can never exist without the change it describes.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

import structlog
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from pydantic import BaseModel, ValidationError

from apps.actions.context import ActionContext
from apps.actions.journal import attach_run, persist_changes
from apps.actions.models import IdempotencyRecord
from apps.actions.registry import ActionSpec, get_action
from apps.audit.services import record_event
from apps.common.context import actor_id_var, channel_var, organization_id_var
from apps.common.exceptions import (
    Conflict,
    DomainError,
    Forbidden,
    Invalid,
    NotFound,
    RateLimited,
)

logger = structlog.get_logger("apps.actions")

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _rate_limit(ctx: ActionContext, spec: ActionSpec) -> None:
    """Per credential (or per user) and minute. Fails open: a cache outage must not stop work."""
    limit = (
        settings.ACTIONS_RATE_WRITE_PER_MINUTE
        if spec.write
        else settings.ACTIONS_RATE_READ_PER_MINUTE
    )
    if limit <= 0:
        return
    subject = ctx.credential_id or str(ctx.user.pk)
    bucket = int(time.time() // 60)
    key = f"actions:rate:{'w' if spec.write else 'r'}:{subject}:{bucket}"
    try:
        cache.add(key, 0, 120)
        used = cache.incr(key)
    except Exception:
        return
    if used > limit:
        raise RateLimited("Too many calls; slow down.", extra={"retry_after": 60})


def _check_access(ctx: ActionContext, spec: ActionSpec) -> None:
    if ctx.channel not in spec.channels:
        raise NotFound("Unknown action.")  # not Forbidden: do not confirm it exists
    if not ctx.has_scope(spec.scope):
        raise Forbidden(f"This credential lacks the scope {spec.scope}.", code="missing_scope")
    if spec.roles is not None:
        if ctx.role not in spec.roles:
            raise Forbidden("Your role cannot do this.", code="role_forbidden")
    elif spec.write and not ctx.can_write:
        raise Forbidden("Your role is read-only.", code="read_only_role")


def _parse(spec: ActionSpec, payload: dict[str, Any] | None) -> BaseModel | None:
    if spec.input_model is None:
        if payload:
            raise Invalid("This action takes no input.")
        return None
    try:
        return spec.input_model.model_validate(payload or {})
    except ValidationError as exc:
        # Field names and messages only: ``input`` would echo user data (possibly PII) back
        # into responses, logs and traces.
        errors = [
            {"field": ".".join(str(part) for part in e["loc"]), "message": e["msg"]}
            for e in exc.errors(include_input=False, include_url=False, include_context=False)
        ]
        raise Invalid("Invalid input.", extra=errors) from exc


def _request_hash(spec: ActionSpec, parsed: BaseModel | None) -> str:
    body = parsed.model_dump(mode="json") if parsed is not None else {}
    canonical = json.dumps({"a": spec.name, "d": body}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _claim(
    ctx: ActionContext, spec: ActionSpec, key: str, request_hash: str
) -> tuple[IdempotencyRecord | None, dict[str, Any] | None]:
    """Create the claim, or return the stored response of the call that already made it."""
    try:
        with transaction.atomic():
            record = IdempotencyRecord.objects.create(
                organization=ctx.organization,
                actor_id=ctx.user.pk,
                key=key,
                action=spec.name,
                request_hash=request_hash,
            )
        return record, None
    except IntegrityError:
        existing = IdempotencyRecord.objects.get(
            organization=ctx.organization, actor_id=ctx.user.pk, key=key
        )
        if existing.action != spec.name or existing.request_hash != request_hash:
            raise Conflict(
                "This Idempotency-Key was already used for a different request.",
                code="idempotency_key_reused",
            ) from None
        return None, existing.response or {}


def _run(
    ctx: ActionContext, spec: ActionSpec, parsed: BaseModel | None, idempotency_key: str | None
) -> tuple[dict[str, Any], bool]:
    claimed: IdempotencyRecord | None = None
    with transaction.atomic():
        run = attach_run(ctx)
        if idempotency_key:
            claimed, replay = _claim(ctx, spec, idempotency_key, _request_hash(spec, parsed))
            if replay is not None:
                return replay, True
        try:
            result = spec.fn(ctx, parsed) if parsed is not None else spec.fn(ctx)
        except ObjectDoesNotExist as exc:
            raise NotFound("Not found.") from exc
        except PermissionDenied as exc:
            raise Forbidden("Not allowed.") from exc
        except DjangoValidationError as exc:
            raise Invalid("Invalid input.", extra=exc.messages) from exc
        output = _to_output(spec, result)
        persist_changes(ctx, spec.name, run)
        if spec.audit:
            record_event(
                action=f"action.{spec.name}",
                actor=ctx.user,
                organization=ctx.organization,
                target=ctx.target,
                metadata={"channel": ctx.channel, "credential": ctx.credential_id or ""},
            )
        if claimed is not None:
            claimed.response = output
            claimed.save(update_fields=["response_json", "updated_at"])
    return output, False


def _to_output(spec: ActionSpec, result: Any) -> dict[str, Any]:
    if spec.output_model is None:
        return {}
    if isinstance(result, spec.output_model):
        return result.model_dump(mode="json")
    # Accept a mapping too, validated against the declared model: the contract is the model.
    return spec.output_model.model_validate(result).model_dump(mode="json")


def invoke(
    name: str,
    ctx: ActionContext,
    payload: dict[str, Any] | None = None,
    *,
    idempotency_key: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Run action ``name`` for ``ctx``. Returns ``(output, replayed)``.

    Raises a :class:`~apps.common.exceptions.DomainError` for every refusal; anything else is
    a bug and propagates.
    """
    spec = get_action(name)
    if spec is None:
        raise NotFound("Unknown action.")
    if idempotency_key is not None and not IDEMPOTENCY_KEY_PATTERN.fullmatch(idempotency_key):
        raise Invalid("Idempotency-Key must be 1-128 characters of A-Z a-z 0-9 . _ : -")

    tokens = (
        organization_id_var.set(str(ctx.organization.pk)),
        actor_id_var.set(str(ctx.user.pk)),
        channel_var.set(ctx.channel),
    )
    started = time.monotonic()
    outcome = "ok"
    try:
        try:
            _check_access(ctx, spec)
        except Forbidden as denial:
            outcome = denial.code
            record_event(
                action=f"action.{spec.name}",
                actor=ctx.user,
                organization=ctx.organization,
                success=False,
                metadata={"channel": ctx.channel, "reason": denial.code},
            )
            raise
        _rate_limit(ctx, spec)
        parsed = _parse(spec, payload)
        output, replayed = _run(ctx, spec, parsed, idempotency_key)
        if replayed:
            outcome = "replayed"
        return output, replayed
    except DomainError as error:
        outcome = outcome if outcome != "ok" else error.code
        raise
    except Exception:
        outcome = "error"
        logger.exception("action_failed", action=spec.name)
        raise
    finally:
        logger.info(
            "action_invoked",
            action=spec.name,
            outcome=outcome,
            duration_ms=round((time.monotonic() - started) * 1000, 1),
            write=spec.write,
        )
        organization_id_var.reset(tokens[0])
        actor_id_var.reset(tokens[1])
        channel_var.reset(tokens[2])
