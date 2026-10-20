from __future__ import annotations

import threading
from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth.signals import user_login_failed
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.integrity import prune, verify_all, verify_chain
from apps.audit.models import GENESIS, SYSTEM_CHAIN, AuditAnchor, AuditEvent
from apps.audit.services import record_event
from apps.organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db(transaction=True)
on_postgres = connection.vendor == "postgresql"
needs_postgres = pytest.mark.skipif(not on_postgres, reason="needs PostgreSQL")
not_postgres = pytest.mark.skipif(
    on_postgres, reason="PostgreSQL's trigger forbids the edits these tests simulate"
)


def events(org: Organization | None, count: int) -> list[AuditEvent]:
    return [record_event(action=f"test.step{n}", organization=org) for n in range(count)]


def test_events_form_one_chain_per_organization_and_one_for_the_system(
    organization: Organization,
) -> None:
    other = Organization.objects.create(name="B", slug="bee-org")
    a = events(organization, 3)
    b = events(other, 2)
    s = events(None, 2)
    assert [e.seq for e in a] == [1, 2, 3] and [e.seq for e in b] == [1, 2]
    assert a[0].prev_hash == GENESIS and a[1].prev_hash == a[0].hash
    assert s[0].chain_key == SYSTEM_CHAIN and s[1].prev_hash == s[0].hash
    assert all(r.ok for r in verify_all())


@not_postgres
def test_editing_a_stored_event_is_detected() -> None:
    _, second, _ = events(None, 3)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE audit_auditevent SET action = %s WHERE id = %s", ["x", second.pk.hex]
        )
    report = verify_chain(SYSTEM_CHAIN)
    assert not report.ok and any("does not match" in p for p in report.problems)


@not_postgres
def test_removing_an_event_leaves_a_gap_and_a_broken_link() -> None:
    _, second, _ = events(None, 3)
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM audit_auditevent WHERE id = %s", [second.pk.hex])
    report = verify_chain(SYSTEM_CHAIN)
    assert not report.ok
    assert any("gap" in p for p in report.problems) and any("link" in p for p in report.problems)


def test_deleting_a_user_or_organization_never_touches_the_trail(
    user: User, organization: Organization, membership: Membership
) -> None:
    """Audit finding #3: SET_NULL rewrote audit rows when their user or tenant was deleted."""
    event = record_event(action="test.owned", actor=user, organization=organization)
    before = AuditEvent.objects.values().get(pk=event.pk)
    Membership.objects.all().delete()
    user.delete()
    organization.delete()
    after = AuditEvent.objects.values().get(pk=event.pk)
    assert before == after and after["actor_id"] is not None
    assert verify_chain(str(before["organization_id"])).ok


@pytest.mark.parametrize(
    "metadata",
    [
        {"user_email": "x"},
        {"cpf_number": "1"},
        {"access_token": "t"},
        {"note": "write to maria@example.com"},
        {"note": "cpf 123.456.789-09"},
        {"note": "x" * 500},
        {"a": {"b": {"c": {"d": {"e": 1}}}}},
        {"Bad-Key": 1},
        {"blob": object()},
    ],
)
def test_metadata_rejects_personal_data_in_keys_and_values(metadata: dict[str, Any]) -> None:
    """Audit finding #13: only exact key matches were rejected and values were never read."""
    with pytest.raises(ValidationError):
        record_event(action="test.meta", metadata=metadata)


def test_metadata_accepts_the_shapes_the_platform_itself_writes() -> None:
    record_event(
        action="test.meta",
        metadata={"channel": "mcp", "credential": "", "fields": ["full_name"], "scope_count": 3},
    )


def test_failed_logins_are_coalesced_per_client_and_account() -> None:
    """Audit finding #14: every attempt of a brute-force run was written, forever."""
    cache.clear()
    for _ in range(25):
        user_login_failed.send(sender=None, credentials={"username": "v@example.com"}, request=None)
    user_login_failed.send(sender=None, credentials={"username": "other@example.com"}, request=None)
    assert AuditEvent.objects.filter(action="auth.login_failed").count() == 2


@not_postgres
def test_pruning_old_events_keeps_the_rest_verifiable() -> None:
    old = events(None, 3)
    AuditEvent._base_manager.filter(pk__in=[e.pk for e in old]).update(
        occurred_at=timezone.now() - timedelta(days=400)
    )
    fresh = events(None, 2)
    result = prune(30)
    assert result["total"] == 3
    anchor = AuditAnchor.objects.get(chain_key=SYSTEM_CHAIN)
    assert anchor.seq == 3 and anchor.hash == old[-1].hash
    assert verify_chain(SYSTEM_CHAIN).ok  # what remains still verifies from the anchor
    nxt = record_event(action="test.after")
    assert nxt.seq == 6 and nxt.prev_hash == fresh[-1].hash and verify_chain(SYSTEM_CHAIN).ok


@needs_postgres
def test_the_database_itself_refuses_to_rewrite_the_trail() -> None:
    from django.db import DatabaseError

    event = events(None, 1)[0]
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE audit_auditevent ENABLE TRIGGER audit_auditevent_no_truncate")
    for sql in (
        "UPDATE audit_auditevent SET action = 'x'",
        "DELETE FROM audit_auditevent",
        "TRUNCATE audit_auditevent",
    ):
        with pytest.raises(DatabaseError), connection.cursor() as cursor:
            cursor.execute(sql)
        connection.close()  # an aborted statement poisons the connection
    assert AuditEvent.objects.filter(pk=event.pk).exists()
    with connection.cursor() as cursor:  # back to the state the other tests rely on
        cursor.execute("ALTER TABLE audit_auditevent DISABLE TRIGGER audit_auditevent_no_truncate")


@needs_postgres
def test_pruning_works_through_the_trigger_only_inside_maintenance() -> None:
    events(None, 2)
    AuditEvent._base_manager.count()
    result = prune(0)  # everything is older than "now"
    assert result["total"] == 2
    nxt = record_event(action="test.after_prune")
    assert nxt.seq == 3 and verify_chain(SYSTEM_CHAIN).ok


@needs_postgres
def test_concurrent_writers_of_one_chain_never_fork_it() -> None:
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for _ in range(10):
                record_event(action="test.race")
        except BaseException as exc:
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    report = verify_chain(SYSTEM_CHAIN)
    assert report.ok and report.checked == 50
