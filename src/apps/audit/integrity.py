"""Verifying and pruning the audit chain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.db import connection, transaction
from django.utils import timezone

from apps.audit.models import GENESIS, AuditAnchor, AuditEvent


@dataclass
class ChainReport:
    chain_key: str
    checked: int = 0
    problems: list[str] = field(default_factory=list)
    last_hash: str = ""
    last_seq: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems


Heads = dict[str, dict[str, Any]]


def verify_chain(
    chain_key: str, *, batch: int = 2000, expect: dict[str, Any] | None = None
) -> ChainReport:
    """Walk one chain in order and recompute every hash.

    Detects an altered row (its stored hash no longer matches its content), a removed or
    inserted row (a gap in ``seq`` or a broken ``prev_hash`` link) and a chain whose start does
    not match the recorded prune anchor. Rows written before chaining existed (empty hash) are
    outside any chain and are not checked.

    ``expect`` is a head recorded earlier *somewhere the database cannot reach*
    (``{"seq": n, "hash": "..."}``). Without it the newest rows are the one thing a chain cannot
    vouch for: deleting them leaves a shorter chain that still verifies.
    """
    report = ChainReport(chain_key)
    anchor = AuditAnchor.objects.filter(chain_key=chain_key).first()
    expected_prev = anchor.hash if anchor else GENESIS
    expected_seq = (anchor.seq + 1) if anchor else 1
    queryset = AuditEvent.objects.filter(chain_key=chain_key, seq__isnull=False).order_by("seq")
    for event in queryset.iterator(chunk_size=batch):
        if event.seq != expected_seq:
            report.problems.append(f"gap before seq {event.seq} (expected {expected_seq})")
            expected_seq = int(event.seq or 0)
        if event.prev_hash != expected_prev:
            report.problems.append(f"seq {event.seq}: link to the previous event is broken")
        if event.compute() != event.hash:
            report.problems.append(f"seq {event.seq} ({event.id}): content does not match its hash")
        expected_prev, expected_seq = event.hash, expected_seq + 1
        report.checked += 1
        report.last_hash, report.last_seq = event.hash, int(event.seq or 0)
    if expect:
        _check_expected_head(report, chain_key, expect, anchor)
    return report


def _check_expected_head(
    report: ChainReport, chain_key: str, expect: dict[str, Any], anchor: AuditAnchor | None
) -> None:
    seq, digest = int(expect["seq"]), str(expect["hash"])
    if anchor is not None and seq <= anchor.seq:
        if seq == anchor.seq and anchor.hash != digest:
            report.problems.append(f"the prune anchor at seq {seq} differs from the recorded head")
        return  # older than the anchor: pruned on purpose, nothing left to compare
    if report.last_seq < seq:
        report.problems.append(
            f"newest events are missing: head is seq {report.last_seq}, {seq} was recorded"
        )
        return
    stored = AuditEvent.objects.filter(chain_key=chain_key, seq=seq).values_list("hash", flat=True)
    found = stored.first()
    if found is None:
        report.problems.append(f"seq {seq} (a recorded head) is no longer in the chain")
    elif found != digest:
        report.problems.append(f"seq {seq} differs from the head that was recorded for it")


def chain_keys() -> list[str]:
    return list(
        AuditEvent.objects.filter(seq__isnull=False)
        .order_by()
        .values_list("chain_key", flat=True)
        .distinct()
    )


def verify_all(expected: Heads | None = None) -> list[ChainReport]:
    expected = expected or {}
    keys = sorted(set(chain_keys()) | set(expected))
    return [verify_chain(key, expect=expected.get(key)) for key in keys]


def heads(reports: list[ChainReport]) -> Heads:
    """The newest hash of every chain, in the shape ``verify_chain(expect=...)`` reads back."""
    return {r.chain_key: {"seq": r.last_seq, "hash": r.last_hash} for r in reports if r.last_hash}


def prune(older_than_days: int) -> dict[str, Any]:
    """Delete events past retention and remember where each chain was cut.

    Only the oldest prefix of a chain is ever removed, so the remaining chain still verifies
    from the recorded anchor. On PostgreSQL the delete goes through ``audit_prune()``, the one
    function the trigger lets delete (and only for the role that owns the table). Returns counts
    per chain.
    """
    cutoff = timezone.now() - timedelta(days=older_than_days)
    removed: dict[str, int] = {}
    with transaction.atomic():
        for key in chain_keys():
            doomed = AuditEvent.objects.filter(chain_key=key, seq__isnull=False).order_by("seq")
            keep_from = doomed.filter(occurred_at__gte=cutoff).values_list("seq", flat=True).first()
            prefix = doomed if keep_from is None else doomed.filter(seq__lt=keep_from)
            last = prefix.order_by("-seq").values("seq", "hash").first()
            if last is None:
                continue
            up_to = int(last["seq"] or 0)
            AuditAnchor.objects.update_or_create(
                chain_key=key, defaults={"seq": up_to, "hash": last["hash"]}
            )
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT audit_prune(%s, %s)", [key, up_to])
                    removed[key] = int(cursor.fetchone()[0])
            else:
                # QuerySet.delete is blocked on purpose (AppendOnlyQuerySet); the maintenance
                # path uses the base manager. SQLite has no trigger to get past.
                ids = list(prefix.values_list("pk", flat=True))
                AuditEvent._base_manager.filter(pk__in=ids).delete()
                removed[key] = len(ids)
    return {"removed": removed, "total": sum(removed.values())}
