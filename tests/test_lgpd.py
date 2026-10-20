"""LGPD: the catalog, consent integrity, rights requests end to end, retention and deadlines."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.signing import TimestampSigner
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.apikeys.models import ApiKey
from apps.audit.integrity import verify_all
from apps.examples.models import Note
from apps.flows.models import FlowRun
from apps.organizations.models import Membership, Organization
from apps.privacy import services
from apps.privacy.baseline import BASELINE_CODES
from apps.privacy.catalog import CATALOG, unclassified
from apps.privacy.deadlines import add_business_days, business_days_between
from apps.privacy.models import (
    ConsentRecord,
    DataSubject,
    DataSubjectRequest,
    LegalHold,
    PersonalDataIncident,
    PrivacyNotice,
    ProcessingPurpose,
)
from apps.privacy.retention import sweep

pytestmark = pytest.mark.django_db
Status = DataSubjectRequest.Status
Type = DataSubjectRequest.RequestType


@pytest.fixture(autouse=True)
def seeded(db: object) -> None:
    call_command("privacy_seed")
    cache.clear()
    mail.outbox.clear()


@pytest.fixture
def notice(db: object) -> PrivacyNotice:
    return PrivacyNotice.objects.create(
        version="1",
        document_url="https://example.com/privacy/1",
        checksum_sha256="a" * 64,
        effective_at=timezone.now(),
        active=True,
    )


@pytest.fixture
def consent_purpose(db: object) -> ProcessingPurpose:
    return ProcessingPurpose.objects.create(
        code="newsletter",
        name="Newsletter",
        description="Product news.",
        lawful_basis="consent",
        data_categories=["contact"],
        retention_days=365,
        cookie_category="marketing",
    )


def make_request(user: User, kind: str) -> DataSubjectRequest:
    return DataSubjectRequest.objects.create(
        requester=user,
        subject=DataSubject.for_user(user),
        request_type=kind,
        identity_verified_at=timezone.now(),
    )


# --- the catalog --------------------------------------------------------------------------


def test_every_model_has_been_classified() -> None:
    """The guardrail: a new model without a privacy decision fails here, in CI."""
    assert unclassified() == [], (
        "Classify these in <app>/privacy.py (personal(...) or not_personal(..., reason)): "
        f"{unclassified()}"
    )


def test_catalog_entries_are_internally_consistent() -> None:
    for item in CATALOG.values():
        field_names = {f.name for f in item.model._meta.get_fields()}
        if not item.personal:
            assert item.reason, item.label
            continue
        assert item.purpose in BASELINE_CODES, f"{item.label}: unknown purpose {item.purpose}"
        assert set(item.fields) <= field_names | {"password"}, item.label
        if item.retention_field:
            assert item.retention_field in field_names, item.label
        if item.on_erase == "keep":
            assert item.reason, item.label


def test_ropa_lists_every_personal_table_with_its_purpose(
    capsys: pytest.CaptureFixture[str],
) -> None:
    call_command("privacy_ropa")
    ropa = json.loads(capsys.readouterr().out)
    tables = {op["table"]: op for op in ropa["operations"]}
    assert tables["examples.note"]["purpose"] == "product-content"
    assert tables["examples.note"]["lawful_basis"] == "contract"
    assert tables["privacy.consentrecord"]["on_erase"] == "keep"
    assert tables["privacy.consentrecord"]["kept_because"]


# --- notices and consent ------------------------------------------------------------------


def test_a_notice_cannot_be_rewritten_and_only_one_is_active(notice: PrivacyNotice) -> None:
    """Audit #17: editing the text in place changed what past consents seemed to attest to."""
    notice.document_url = "https://evil.example/changed"
    with pytest.raises(ValidationError):
        notice.save()
    newer = PrivacyNotice.objects.create(
        version="2",
        document_url="https://example.com/privacy/2",
        checksum_sha256="b" * 64,
        effective_at=timezone.now(),
        active=True,
    )
    notice.refresh_from_db()
    assert newer.active and not notice.active


def test_consent_records_freeze_what_was_shown_and_form_a_chain(
    user: User, notice: PrivacyNotice, consent_purpose: ProcessingPurpose
) -> None:
    client = APIClient()
    client.force_authenticate(user)
    payload = {"purpose": str(consent_purpose.id), "notice": str(notice.id)}
    first = client.post(
        "/api/v1/privacy/consents/", {**payload, "decision": "granted"}, format="json"
    )
    second = client.post(
        "/api/v1/privacy/consents/", {**payload, "decision": "withdrawn"}, format="json"
    )
    assert first.status_code == second.status_code == 201
    records = list(ConsentRecord.objects.filter(user=user).order_by("seq"))
    assert [r.seq for r in records] == [1, 2]
    assert records[1].prev_hash == records[0].hash
    assert records[0].notice_checksum == "a" * 64
    assert records[0].purpose_digest == consent_purpose.digest()
    assert set(records[0].evidence) == {"ip_hash", "ua_hash", "guardian"}
    # Editing the purpose later changes its digest but not what the record attested.
    ProcessingPurpose.objects.filter(pk=consent_purpose.pk).update(description="changed")
    consent_purpose.refresh_from_db()
    assert consent_purpose.digest() != records[0].purpose_digest
    assert records[0].compute_hash() == records[0].hash


def test_consent_state_flags_a_newer_notice_for_renewal(
    user: User, notice: PrivacyNotice, consent_purpose: ProcessingPurpose
) -> None:
    ConsentRecord.objects.create(
        user=user, purpose=consent_purpose, notice=notice, decision="granted"
    )
    client = APIClient()
    client.force_authenticate(user)
    state = client.get("/api/v1/privacy/consents/state/").data
    assert state[0]["decision"] == "granted" and state[0]["needs_renewal"] is False
    PrivacyNotice.objects.create(
        version="2", document_url="https://example.com/2", checksum_sha256="c" * 64,
        effective_at=timezone.now(), active=True,
    )  # fmt: skip
    state = client.get("/api/v1/privacy/consents/state/").data
    assert state[0]["needs_renewal"] is True


def test_children_purposes_need_the_guardian(
    user: User, notice: PrivacyNotice, consent_purpose: ProcessingPurpose
) -> None:
    """LGPD art. 14: a parent or guardian's specific consent."""
    ProcessingPurpose.objects.filter(pk=consent_purpose.pk).update(involves_children=True)
    client = APIClient()
    client.force_authenticate(user)
    body = {"purpose": str(consent_purpose.id), "notice": str(notice.id), "decision": "granted"}
    assert client.post("/api/v1/privacy/consents/", body, format="json").status_code == 400
    ok = client.post(
        "/api/v1/privacy/consents/", {**body, "guardian_confirmed": True}, format="json"
    )
    assert ok.status_code == 201
    assert ConsentRecord.objects.get().evidence["guardian"] is True


# --- the state machine ------------------------------------------------------------------


def test_requests_move_only_along_allowed_transitions(user: User) -> None:
    """Audit #18: statuses could be set to anything, completed without a completion time."""
    request = make_request(user, Type.ACCESS)
    with pytest.raises(ValidationError):
        request.transition_to(Status.COMPLETED)  # received -> completed is not allowed
    request.transition_to(Status.IN_PROGRESS)
    with pytest.raises(ValidationError):
        request.transition_to(Status.DENIED)  # a denial needs a reason
    request.transition_to(Status.COMPLETED, summary="done")
    assert request.completed_at is not None
    with pytest.raises(ValidationError):
        request.transition_to(Status.IN_PROGRESS)  # terminal
    request.status = Status.RECEIVED  # direct edits are caught on save, too
    with pytest.raises(ValidationError):
        request.save()
    with pytest.raises(ValidationError):
        request.delete()


# --- rights, end to end -------------------------------------------------------------------


def test_an_access_request_produces_an_encrypted_export_only_the_requester_can_fetch(
    user: User,
    organization: Organization,
    membership: Membership,
    django_capture_on_commit_callbacks: object,
) -> None:
    Note.objects.create(
        organization=organization, title="Mine", body="secret body", created_by=user
    )
    client = APIClient()
    client.force_authenticate(user)
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        created = client.post(
            "/api/v1/privacy/requests/", {"request_type": "access"}, format="json"
        )
    assert created.status_code == 201
    request = DataSubjectRequest.objects.get(pk=created.data["id"])
    request.refresh_from_db()
    assert request.status == Status.COMPLETED and request.export_name
    assert FlowRun.objects.get(flow="privacy.dsar").status == "completed"

    mail_with_link = next(m for m in mail.outbox if "export" in m.subject.lower())
    link = mail_with_link.body.splitlines()[1].strip()
    token = link.rsplit("/", 2)[-2]
    download = client.get(f"/api/v1/privacy/exports/{token}/")
    assert download.status_code == 200 and download["Cache-Control"] == "no-store"
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        data = json.loads(archive.read("data.json"))
    assert data["records"]["examples.note"][0]["title"] == "Mine"
    assert "password" not in json.dumps(data)

    assert APIClient().get(f"/api/v1/privacy/exports/{token}/").status_code == 404  # not signed in
    assert client.get("/api/v1/privacy/exports/nonsense/").status_code == 404
    with override_settings(PRIVACY_EXPORT_TTL_DAYS=0):
        assert client.get(f"/api/v1/privacy/exports/{token}/").status_code == 404  # expired


def test_stored_exports_are_sealed(user: User) -> None:
    from django.core.files.storage import default_storage

    request = make_request(user, Type.ACCESS)
    name = services.package_export(request)
    raw = default_storage.open(name, "rb").read()
    assert raw[:2] == b"S1" and b"PK" not in raw[:4] and user.email.encode() not in raw


def test_erasure_anonymizes_the_person_and_keeps_the_proof(
    user: User, organization: Organization, membership: Membership, notice: PrivacyNotice,
    consent_purpose: ProcessingPurpose,
) -> None:  # fmt: skip
    note = Note.objects.create(
        organization=organization, title="private", body="b", created_by=user
    )
    key, _ = ApiKey.issue(user=user, organization=organization, label="k", scopes=["notes:read"])
    ConsentRecord.objects.create(
        user=user, purpose=consent_purpose, notice=notice, decision="granted"
    )
    request = make_request(user, Type.DELETION)
    original_email = user.email

    outcome = services.execute_request(request)

    assert outcome["state"] == "completed"
    user.refresh_from_db()
    note.refresh_from_db()
    assert user.email != original_email and user.email.endswith("@anonymized.invalid")
    assert not user.is_active and not user.has_usable_password() and user.anonymized_at
    assert note.title == "[removed]" and note.body == ""
    assert not ApiKey.objects.filter(pk=key.pk).exists()
    assert Membership.objects.get(user=user).is_active is False
    assert ConsentRecord.objects.filter(user=user).count() == 1  # the proof is kept
    subject = DataSubject.objects.get(user=user)
    assert subject.email == "" and subject.anonymized_at
    assert subject.email_index != DataSubject.index_for(original_email)  # no re-identification
    request.refresh_from_db()
    assert request.status == Status.COMPLETED and request.details == ""
    assert all(report.ok for report in verify_all())  # the audit trail is untouched and valid


def test_a_legal_hold_blocks_erasure_and_the_request_is_denied_with_a_reason(
    user: User, organization: Organization
) -> None:
    subject = DataSubject.for_user(user)
    LegalHold.objects.create(subject=subject, reason="Litigation 123")
    note = Note.objects.create(organization=organization, title="evidence", created_by=user)
    request = make_request(user, Type.DELETION)
    outcome = services.execute_request(request)
    request.refresh_from_db()
    note.refresh_from_db()
    assert outcome["state"] == "denied" and request.denial_reason_code == "legal_hold"
    assert note.title == "evidence"


def test_blocking_stops_processing_and_cuts_credentials(
    user: User, organization: Organization, membership: Membership
) -> None:
    key, _ = ApiKey.issue(user=user, organization=organization, label="k", scopes=["notes:read"])
    request = make_request(user, Type.BLOCKING)
    assert services.execute_request(request)["state"] == "completed"
    user.refresh_from_db()
    key.refresh_from_db()
    assert not user.is_active and key.revoked_at is not None
    assert DataSubject.objects.get(user=user).blocked_at


def test_withdrawing_all_consent_through_a_request(
    user: User, notice: PrivacyNotice, consent_purpose: ProcessingPurpose
) -> None:
    ConsentRecord.objects.create(
        user=user, purpose=consent_purpose, notice=notice, decision="granted"
    )
    assert (
        services.execute_request(make_request(user, Type.CONSENT_WITHDRAWAL))["state"]
        == "completed"
    )
    assert ConsentRecord.objects.filter(user=user).order_by("seq").last().decision == "withdrawn"


def test_nothing_is_done_for_an_unverified_identity(user: User) -> None:
    request = DataSubjectRequest.objects.create(
        subject=DataSubject.for_user(user), request_type=Type.DELETION, status=Status.VERIFYING
    )
    from apps.common.exceptions import Forbidden

    with pytest.raises(Forbidden):
        services.execute_request(request)
    assert User.objects.get(pk=user.pk).is_active


def test_requests_the_platform_cannot_decide_wait_for_a_person_and_remind_once(user: User) -> None:
    request = make_request(user, Type.CORRECTION)
    outcome = services.execute_request(request)
    request.refresh_from_db()
    assert outcome["state"] == "needs_review" and request.status == Status.LEGAL_REVIEW
    DataSubjectRequest.objects.filter(pk=request.pk).update(
        target_due_at=timezone.now() + timedelta(days=4)
    )
    request.refresh_from_db()
    assert services.send_reminders(request) == ["due_in_5_days"]
    assert services.send_reminders(request) == []  # idempotent
    assert [m.to for m in mail.outbox] == [["dpo@example.test"]]
    DataSubjectRequest.objects.filter(pk=request.pk).update(
        target_due_at=timezone.now() - timedelta(hours=1)
    )
    request.refresh_from_db()
    assert set(services.send_reminders(request)) == {"due_in_1_day", "overdue"}

    services.finish_review(request, outcome="completed", summary="Corrected.")
    request.refresh_from_db()
    assert request.status == Status.COMPLETED


# --- requests without an account ------------------------------------------------------------


def test_public_requests_never_reveal_whether_an_address_is_known(user: User) -> None:
    client = APIClient()
    known = client.post(
        "/api/v1/privacy/public/requests/",
        {"email": user.email, "request_type": "access"},
        format="json",
    )
    unknown = client.post(
        "/api/v1/privacy/public/requests/",
        {"email": "nobody@example.com", "request_type": "access"},
        format="json",
    )
    assert known.status_code == unknown.status_code == 202 and known.data == unknown.data


def test_a_public_request_does_nothing_until_the_email_is_confirmed(user: User) -> None:
    client = APIClient()
    client.post(
        "/api/v1/privacy/public/requests/",
        {"email": "lead@example.com", "request_type": "access"},
        format="json",
    )
    request = DataSubjectRequest.objects.get()
    assert request.status == Status.VERIFYING and request.requester is None
    assert not FlowRun.objects.exists()
    token = TimestampSigner(salt=services.VERIFY_SALT).sign(str(request.pk))
    assert (
        client.post("/api/v1/privacy/public/verify/", {"token": "bad"}, format="json").status_code
        == 422
    )
    done = client.post("/api/v1/privacy/public/verify/", {"token": token}, format="json")
    assert done.status_code == 200
    request.refresh_from_db()
    assert request.status == Status.COMPLETED and request.identity_verified_at
    assert (
        client.post("/api/v1/privacy/public/verify/", {"token": token}, format="json").status_code
        == 422
    )
    assert any("export" in m.subject.lower() and m.to == ["lead@example.com"] for m in mail.outbox)


def test_one_address_cannot_be_used_to_flood_a_third_party() -> None:
    client = APIClient()
    for _ in range(6):
        client.post(
            "/api/v1/privacy/public/requests/",
            {"email": "victim@example.com", "request_type": "access"},
            format="json",
        )
    assert DataSubjectRequest.objects.count() == 3


def test_public_intake_can_be_switched_off() -> None:
    with override_settings(PRIVACY_PUBLIC_REQUESTS=False):
        response = APIClient().post(
            "/api/v1/privacy/public/requests/",
            {"email": "a@example.com", "request_type": "access"},
            format="json",
        )
    assert response.status_code == 404


# --- transparency -----------------------------------------------------------------------


def test_transparency_and_cookie_endpoints_are_public(
    notice: PrivacyNotice, consent_purpose: ProcessingPurpose
) -> None:
    with override_settings(DPO_NAME="Maria DPO", DPO_EMAIL="dpo@example.com"):
        page = APIClient().get("/api/v1/privacy/transparency/").data
    assert page["dpo"]["email"] == "dpo@example.com"
    assert page["notice"]["version"] == "1" and any(
        p["code"] == "newsletter" for p in page["purposes"]
    )
    cookies = APIClient().get("/api/v1/privacy/cookies/").data
    assert cookies["notice_id"] == str(notice.pk)
    assert cookies["categories"][0]["category"] == "marketing"


# --- retention -------------------------------------------------------------------------------


def test_retention_anonymizes_expired_data_and_respects_dry_runs_and_holds(
    user: User, organization: Organization
) -> None:
    old = Note.objects.create(organization=organization, title="old", body="x", created_by=user)
    Note.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=2000))
    fresh = Note.objects.create(organization=organization, title="fresh", created_by=user)

    dry = sweep(dry_run=True)
    assert dry["models"]["examples.note"]["expired"] == 1
    old.refresh_from_db()
    assert old.title == "old"

    LegalHold.objects.create(subject=DataSubject.for_user(user), reason="case")
    assert "examples.note" not in sweep()["models"]
    LegalHold.objects.update(released_at=timezone.now())

    result = sweep()
    assert result["total"] >= 1
    old.refresh_from_db()
    fresh.refresh_from_db()
    assert old.title == "[removed]" and fresh.title == "fresh"


# --- deadlines -------------------------------------------------------------------------------


def test_business_day_arithmetic_skips_weekends_and_listed_holidays() -> None:
    friday = datetime(2026, 10, 23, 10, 0, tzinfo=UTC)
    assert add_business_days(friday, 3) == datetime(2026, 10, 28, 10, 0, tzinfo=UTC)
    with override_settings(PRIVACY_HOLIDAYS=["2026-10-26"]):
        assert add_business_days(friday, 3) == datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
    assert business_days_between(friday, add_business_days(friday, 3)) == 3


def test_incident_deadline_is_computed_and_reminders_fire_once(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from apps.flows.jobs_runtime import execute_job

    now = timezone.now()
    incident = PersonalDataIncident.objects.create(
        reference="INC-1",
        discovered_at=now - timedelta(days=5),
        confirmed_at=now - timedelta(days=5),
        relevant_risk_or_harm=True,
        contains_personal_data=True,
        data_categories=["contact"],
        summary="Leak of a contact list.",
    )
    assert incident.notification_deadline_at is not None
    assert incident.notification_deadline_at > incident.confirmed_at
    PersonalDataIncident.objects.filter(pk=incident.pk).update(
        notification_deadline_at=now - timedelta(hours=2)
    )
    assert execute_job("privacy.incident_deadlines")["reminders"] == 2  # 1-day and overdue
    assert execute_job("privacy.incident_deadlines")["reminders"] == 0
    with pytest.raises(ValidationError):
        incident.delete()


def test_dsar_sweep_starts_flows_that_never_started(user: User) -> None:
    from apps.flows.jobs_runtime import execute_job

    request = make_request(user, Type.CONFIRMATION)
    DataSubjectRequest.objects.filter(pk=request.pk).update(
        created_at=timezone.now() - timedelta(minutes=10)
    )
    assert execute_job("privacy.dsar_sweep")["started"] == 1
    request.refresh_from_db()
    assert request.status == Status.COMPLETED
    assert execute_job("privacy.dsar_sweep")["started"] == 0
