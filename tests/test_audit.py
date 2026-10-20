from __future__ import annotations

import pytest
from django.contrib.auth.signals import user_login_failed
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.audit.services import record_event
from apps.common.encryption import blind_index


@pytest.mark.django_db
def test_audit_events_are_immutable_and_reject_sensitive_metadata(user: User) -> None:
    event = record_event(action="test.performed", actor=user, metadata={"result": "ok"})
    event.action = "test.changed"
    with pytest.raises(ValidationError):
        event.save()
    with pytest.raises(ValidationError):
        event.delete()
    with pytest.raises(ValidationError):
        type(event).objects.filter(pk=event.pk).update(action="test.bulk_changed")

    with pytest.raises(ValidationError):
        record_event(
            action="test.bad_metadata",
            actor=user,
            metadata={"context": {"email": "must-not-be-stored"}},
        )


@pytest.mark.django_db
def test_failed_login_is_audited_with_a_hashed_username() -> None:
    user_login_failed.send(
        sender=None,
        credentials={"username": "victim@example.com"},
        request=None,
    )
    event = AuditEvent.objects.get(action="auth.login_failed")
    assert event.success is False
    assert event.actor is None
    assert event.metadata["username_index"] == blind_index(
        "victim@example.com",
        namespace="audit-login-username",
    )
    assert "victim@example.com" not in str(event.metadata)
