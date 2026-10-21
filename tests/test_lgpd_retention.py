"""Erasure and retention reach everything the person left behind, including stored files."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization
from apps.privacy import services
from apps.privacy.models import DataSubject, LegalHold, ProcessingPurpose
from apps.privacy.retention import sweep
from apps.uploads.models import UploadedFile

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _purposes() -> None:
    from django.core.management import call_command

    call_command("privacy_seed")


def _upload(organization: Organization, user: User) -> UploadedFile:
    row = UploadedFile(
        organization=organization,
        uploaded_by=user,
        original_name="cv.pdf",
        content_type="application/pdf",
        size=3,
        sha256="0" * 64,
        scan_status="skipped",
    )
    row.file.save("blob", ContentFile(b"pdf"), save=False)
    row.save()
    return row


def test_erasing_a_person_deletes_their_stored_files_too(
    user: User,
    organization: Organization,
    membership: Membership,
    django_capture_on_commit_callbacks: Any,
) -> None:
    row = _upload(organization, user)
    storage, name = row.file.storage, row.file.name
    assert storage.exists(name)
    with django_capture_on_commit_callbacks(execute=True):
        report = services.erase_subject(DataSubject.for_user(user))
    assert report["uploads.uploadedfile"] == {"deleted": 1}
    assert not UploadedFile.objects.filter(pk=row.pk).exists()
    assert not storage.exists(name)  # the file left the bucket, not just the table


def test_a_rolled_back_delete_keeps_its_file(
    user: User,
    organization: Organization,
    membership: Membership,
    django_capture_on_commit_callbacks: Any,
) -> None:
    from django.db import transaction

    row = _upload(organization, user)
    pk, storage, name = row.pk, row.file.storage, row.file.name

    class Boom(Exception):
        pass

    with (
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(Boom),
        transaction.atomic(),
    ):
        row.delete()
        raise Boom
    assert UploadedFile.objects.filter(pk=pk).exists() and storage.exists(name)


def test_retention_deletes_expired_uploads_and_their_files(
    user: User,
    organization: Organization,
    membership: Membership,
    django_capture_on_commit_callbacks: Any,
) -> None:
    old, fresh = _upload(organization, user), _upload(organization, user)
    UploadedFile.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=4000))
    with django_capture_on_commit_callbacks(execute=True):
        report = sweep()
    assert report["models"]["uploads.uploadedfile"]["expired"] == 1
    assert not old.file.storage.exists(old.file.name)
    assert fresh.file.storage.exists(fresh.file.name)


def test_dormant_accounts_are_anonymized_but_staff_active_and_held_ones_are_not() -> None:
    long_ago = timezone.now() - timedelta(days=4000)
    dormant = User.objects.create_user(email="dormant@example.com", password="x" * 14)
    never = User.objects.create_user(email="never@example.com", password="x" * 14)
    active = User.objects.create_user(email="active@example.com", password="x" * 14)
    staff = User.objects.create_user(email="staff@example.com", password="x" * 14, is_staff=True)
    held = User.objects.create_user(email="held@example.com", password="x" * 14)
    for person in (dormant, staff, held):
        User.objects.filter(pk=person.pk).update(last_login=long_ago, date_joined=long_ago)
    User.objects.filter(pk=never.pk).update(date_joined=long_ago)  # never signed in, ancient
    User.objects.filter(pk=active.pk).update(last_login=timezone.now())
    LegalHold.objects.create(subject=DataSubject.for_user(held), reason="litigation")

    dry = sweep(dry_run=True)
    assert dry["models"]["accounts.user"]["expired"] == 2
    assert User.objects.get(pk=dormant.pk).anonymized_at is None  # a dry run changes nothing

    sweep()
    for person, gone in (
        (dormant, True),
        (never, True),
        (active, False),
        (staff, False),
        (held, False),
    ):
        person.refresh_from_db()
        assert (person.anonymized_at is not None) is gone, person.email
    assert User.objects.get(pk=dormant.pk).email.endswith("@anonymized.invalid")


def test_the_published_audit_retention_matches_the_prune_job() -> None:
    from django.conf import settings

    purpose = ProcessingPurpose.objects.get(code="security-and-audit")
    assert purpose.retention_days == settings.AUDIT_RETENTION_DAYS == 365
