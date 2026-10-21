"""The audit trail: append-only, tamper-evident, and independent of the rows it describes.

Three properties, each closing a gap that "append-only in the ORM" alone leaves open:

* **No cascade.** ``actor`` and ``organization`` are foreign keys without a database
  constraint and with ``DO_NOTHING``. Deleting a user or an organization never touches an audit
  row (the old ``SET_NULL`` rewrote them, erasing who did what).
* **Keyed hash chain.** Every event stores the hash of the previous event of its chain (one
  chain per organization, plus one for system events) and its own HMAC over its content, keyed
  by ``AUDIT_HMAC_KEY`` (environment, never the database). Changing, inserting or removing a
  row anywhere in the middle breaks every later hash, and a database writer cannot re-chain
  consistently without the key; ``manage.py audit_verify`` finds it. A chain per organization
  keeps writers of different tenants from serializing behind one lock.
* **Database trigger** (PostgreSQL). ``UPDATE``, ``DELETE`` and ``TRUNCATE`` on the table
  raise, so SQL typed into a console is refused too. Deleting is possible only through
  ``audit_prune()`` (retention), and only for the role that owns the table: a runtime role that
  is *not* the owner cannot delete, update or disable anything. That separation is what makes
  "a compromised application account cannot rewrite the trail" true; see the hardening guide.
* **Check constraint.** A row without ``seq`` or ``hash`` is refused, so a forged INSERT cannot
  hide outside the chain.

What this does *not* defend against: the table owner or a database superuser who also holds
``AUDIT_HMAC_KEY``, and deletion of the *newest* rows (the chain only proves what precedes the
head). The scheduled ``audit.verify`` job logs each chain head; ship those lines somewhere the
database cannot reach, and pass them back with ``audit_verify --expect`` to catch tail removal.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC
from typing import Any, NoReturn

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models, transaction
from django.db.models.base import ModelBase
from django.utils import timezone

from apps.common.encryption import chain_digest
from apps.common.logging import redact
from apps.common.models import AppendOnlyQuerySet

GENESIS = "0" * 64
SYSTEM_CHAIN = "system"
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
MAX_METADATA_BYTES = 4096
MAX_VALUE_LENGTH = 200
MAX_DEPTH = 3

# Key fragments that name personal data. The old validator compared whole keys, so
# ``user_email`` or ``cpf_number`` slipped through; fragments catch the family.
SENSITIVE_FRAGMENTS = (
    "address",
    "authorization",
    "birth",
    "cnpj",
    "cookie",
    "cpf",
    "document",
    "dob",
    "email",
    "first_name",
    "last_name",
    "full_name",
    "ip_address",
    "name",
    "password",
    "phone",
    "secret",
    "session",
    "token",
    "username",
    "user_agent",
    "api_key",
)
# Whole keys that contain a sensitive fragment but are safe by design (hashes, ids, labels).
SAFE_KEYS = {"username_index", "ip_hash", "field_names", "fields", "credential", "scope_count"}


def _check_value(value: Any, path: str, depth: int) -> None:
    if depth > MAX_DEPTH:
        raise ValidationError(f"Audit metadata is nested too deeply at {path}.")
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key)
            if not KEY_PATTERN.fullmatch(name):
                raise ValidationError(f"Audit metadata key {name!r} must be snake_case.")
            lowered = name.casefold()
            if lowered not in SAFE_KEYS and any(f in lowered for f in SENSITIVE_FRAGMENTS):
                raise ValidationError(f"Audit metadata key {name!r} looks like personal data.")
            _check_value(child, f"{path}.{name}", depth + 1)
    elif isinstance(value, list | tuple):
        if len(value) > 50:
            raise ValidationError(f"Audit metadata list at {path} is too long.")
        for child in value:
            _check_value(child, path, depth + 1)
    elif isinstance(value, str):
        if len(value) > MAX_VALUE_LENGTH:
            raise ValidationError(f"Audit metadata value at {path} is too long.")
        if redact(value) != value:
            # The redactor rewrites e-mails, CPF/CNPJ, phones, IPs, tokens: if it would, the
            # value is personal data and has no business in a table that is never deleted.
            raise ValidationError(f"Audit metadata value at {path} contains personal data.")
    elif value is not None and not isinstance(value, bool | int | float):
        raise ValidationError(f"Audit metadata value at {path} has an unsupported type.")


def validate_metadata(value: dict[str, object]) -> None:
    if not isinstance(value, dict):
        raise ValidationError("Audit metadata must be a JSON object.")
    _check_value(value, "metadata", 0)
    if len(json.dumps(value, default=str)) > MAX_METADATA_BYTES:
        raise ValidationError("Audit metadata is too large.")


def compute_hash(
    *,
    prev_hash: str,
    seq: int,
    event_id: Any,
    occurred_at: Any,
    actor_id: Any,
    organization_id: Any,
    action: str,
    target_type: str,
    target_id: str,
    request_id: str,
    ip_hash: str,
    success: bool,
    metadata: Any,
) -> str:
    body = json.dumps(
        {
            "p": prev_hash,
            "n": seq,
            "i": str(event_id),
            "t": occurred_at.astimezone(UTC).isoformat(timespec="microseconds"),
            "a": str(actor_id or ""),
            "o": str(organization_id or ""),
            "x": action,
            "tt": target_type,
            "ti": target_id,
            "r": request_id,
            "h": ip_hash,
            "s": bool(success),
            "m": metadata,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return chain_digest("audit", body)


class AuditEvent(models.Model):
    objects = AppendOnlyQuerySet.as_manager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="+",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="+",
    )
    action = models.CharField(max_length=120, db_index=True)
    target_type = models.CharField(max_length=120, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    success = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True, validators=[validate_metadata])
    chain_key = models.CharField(max_length=40, blank=True, default="")
    seq = models.PositiveBigIntegerField(null=True, blank=True)
    prev_hash = models.CharField(max_length=64, blank=True, default="")
    hash = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ("-occurred_at",)
        indexes = [
            models.Index(fields=("organization", "occurred_at")),
            models.Index(fields=("actor", "occurred_at")),
            models.Index(fields=("action", "occurred_at")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("chain_key", "seq"),
                condition=models.Q(seq__isnull=False),
                name="unique_audit_chain_position",
            ),
            # Every new row belongs to a chain. On PostgreSQL the migration adds this NOT VALID
            # so rows from before chaining existed do not block it; new rows are always checked.
            models.CheckConstraint(
                condition=models.Q(seq__isnull=False) & ~models.Q(hash=""),
                name="audit_event_is_chained",
            ),
        ]

    def _chain(self) -> str:
        return str(self.organization_id) if self.organization_id else SYSTEM_CHAIN

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding:
            raise ValidationError("Audit events are append-only.")
        # Uniqueness and constraint validation would add a SELECT per event on the
        # authentication hot path. The primary key is a client-side UUID and the
        # database still enforces both, so only the field validators are worth running.
        self.full_clean(validate_unique=False, validate_constraints=False)
        with transaction.atomic():
            self.chain_key = self._chain()
            self._lock_chain()
            last = (
                AuditEvent.objects.filter(chain_key=self.chain_key, seq__isnull=False)
                .order_by("-seq")
                .values("seq", "hash")
                .first()
            )
            anchor = (
                AuditAnchor.objects.filter(chain_key=self.chain_key).values("seq", "hash").first()
            )
            if last is not None:
                self.seq, self.prev_hash = int(last["seq"] or 0) + 1, last["hash"]
            elif anchor is not None:
                self.seq, self.prev_hash = int(anchor["seq"]) + 1, anchor["hash"]
            else:
                self.seq, self.prev_hash = 1, GENESIS
            self.hash = self.compute()
            super().save(
                force_insert=True,
                using=using,
            )

    def compute(self) -> str:
        return compute_hash(
            prev_hash=self.prev_hash,
            seq=int(self.seq or 0),
            event_id=self.id,
            occurred_at=self.occurred_at,
            actor_id=self.actor_id,
            organization_id=self.organization_id,
            action=self.action,
            target_type=self.target_type,
            target_id=self.target_id,
            request_id=self.request_id,
            ip_hash=self.ip_hash,
            success=self.success,
            metadata=self.metadata,
        )

    def _lock_chain(self) -> None:
        """Serialize writers of *one* chain for the length of this transaction.

        The advisory lock is released at commit, so the insert should be the last statement of
        the surrounding work. SQLite has a single writer already.
        """
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [self.chain_key])

    def delete(self, using: Any | None = None, keep_parents: bool = False) -> NoReturn:
        raise ValidationError("Audit events cannot be deleted through the application.")

    def __str__(self) -> str:
        return f"{self.occurred_at} {self.action}"


class AuditAnchor(models.Model):
    """Where a chain stood when old events were pruned, so verification can still start there."""

    chain_key = models.CharField(max_length=40, unique=True)
    seq = models.PositiveBigIntegerField()
    hash = models.CharField(max_length=64)
    pruned_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"{self.chain_key}@{self.seq}"
