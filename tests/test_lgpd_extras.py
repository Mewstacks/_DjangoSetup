"""LGPD additions: cookie consent proof, incident deadlines, age assurance, pt-BR messages."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from io import StringIO
from typing import Any

import pytest
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.observability import checks
from apps.privacy import age, messages
from apps.privacy.models import (
    CookieConsent,
    ImpactAssessment,
    PersonalDataIncident,
    PrivacyNotice,
    ProcessingPurpose,
    SubProcessor,
)
from config.settings import validators

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def seeded(db: object) -> None:
    call_command("privacy_seed")
    cache.clear()


@pytest.fixture
def cookie_purposes() -> None:
    ProcessingPurpose.objects.create(
        code="ads",
        name="Ads",
        description="d",
        lawful_basis="consent",
        retention_days=30,
        cookie_category="marketing",
        refusal_consequence="You will see ads that are less relevant.",
    )
    ProcessingPurpose.objects.create(
        code="session",
        name="Session",
        description="d",
        lawful_basis="contract",
        retention_days=30,
        cookie_category="necessary",
    )


# --- cookie consent without an account -----------------------------------------------------


def test_a_cookie_choice_is_recorded_as_proof_with_hashes_only(cookie_purposes: None) -> None:
    PrivacyNotice.objects.create(
        version="1",
        document_url="https://example.com/n",
        checksum_sha256="c" * 64,
        effective_at=timezone.now(),
        active=True,
    )
    visitor = uuid.uuid4()
    reply = APIClient().post(
        "/api/v1/privacy/cookies/consent/",
        {"visitor_id": str(visitor), "categories": {"marketing": True, "necessary": False}},
        format="json",
        HTTP_USER_AGENT="Browser/1.0",
    )
    assert reply.status_code == 201, reply.content
    record = CookieConsent.objects.get(visitor_id=visitor)
    assert record.categories == {
        "marketing": True,
        "necessary": True,
    }  # necessary cannot be refused
    assert record.notice_checksum == "c" * 64
    assert "Browser" not in json.dumps(record.evidence) and "127.0.0.1" not in json.dumps(
        record.evidence
    )
    assert len(record.evidence["ua_hash"]) == 32 and len(record.evidence["ip_hash"]) == 64


def test_a_change_of_mind_is_a_new_row_and_unknown_categories_are_refused(
    cookie_purposes: None,
) -> None:
    visitor = str(uuid.uuid4())
    client = APIClient()
    for accepted in (True, False):
        client.post(
            "/api/v1/privacy/cookies/consent/",
            {"visitor_id": visitor, "categories": {"marketing": accepted}},
            format="json",
        )
    assert CookieConsent.objects.filter(visitor_id=visitor).count() == 2
    bad = client.post(
        "/api/v1/privacy/cookies/consent/",
        {"visitor_id": visitor, "categories": {"tracking-everything": True}},
        format="json",
    )
    assert bad.status_code in (400, 422)
    too_many = client.post(
        "/api/v1/privacy/cookies/consent/",
        {"visitor_id": visitor, "categories": {f"c{n}": True for n in range(11)}},
        format="json",
    )
    assert too_many.status_code == 400


def test_the_consequence_of_refusing_is_published_with_each_purpose(cookie_purposes: None) -> None:
    body = APIClient().get("/api/v1/privacy/transparency/").json()
    ads = next(p for p in body["purposes"] if p["code"] == "ads")
    assert ads["refusal_consequence"].startswith("You will see")


def test_cookie_consent_rows_expire_with_retention() -> None:
    from apps.privacy.retention import sweep

    old = CookieConsent.objects.create(visitor_id=uuid.uuid4(), categories={"necessary": True})
    CookieConsent.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=4000))
    assert sweep()["models"]["privacy.cookieconsent"]["expired"] == 1


# --- incidents --------------------------------------------------------------------------------


def _incident(**extra: Any) -> PersonalDataIncident:
    now = timezone.now()
    return PersonalDataIncident.objects.create(
        reference=extra.pop("reference", "INC-X"),
        discovered_at=now,
        confirmed_at=now,
        relevant_risk_or_harm=True,
        contains_personal_data=True,
        data_categories=["contact"],
        summary="A contact list left a bucket.",
        **extra,
    )


def test_incident_deadlines_cover_the_anpd_the_people_and_the_complement() -> None:
    incident = _incident()
    assert incident.notification_deadline_at == incident.subjects_deadline_at
    assert incident.complement_deadline_at is None
    incident.anpd_notified_at = timezone.now()
    incident.save()
    assert incident.complement_deadline_at is not None
    assert incident.complement_deadline_at - incident.anpd_notified_at >= timedelta(days=27)


@override_settings(PRIVACY_SMALL_AGENT=True)
def test_a_small_agent_gets_the_period_doubled() -> None:
    small = _incident(reference="INC-S")
    with override_settings(PRIVACY_SMALL_AGENT=False):
        normal = _incident(reference="INC-N")
    assert (small.notification_deadline_at - small.confirmed_at) > (
        normal.notification_deadline_at - normal.confirmed_at
    )


def test_the_anpd_export_assembles_the_communication_without_sending_anything() -> None:
    _incident(measures_taken="Rotated the credentials; closed the bucket.")
    out = StringIO()
    call_command("privacy_incident_export", "INC-X", stdout=out)
    data = json.loads(out.getvalue())
    assert data["incident"]["measures_taken"].startswith("Rotated")
    assert data["incident"]["approximate_subject_count"] is None
    assert data["dates"]["notification_deadline_at"] and data["dpo"]["email"] == "dpo@example.test"
    md = StringIO()
    call_command("privacy_incident_export", "INC-X", "--format", "md", stdout=md)
    assert md.getvalue().startswith("# Incident INC-X")
    with pytest.raises(Exception, match="No incident"):
        call_command("privacy_incident_export", "NOPE", stdout=StringIO())


# --- art. 14 and the ECA Digital ------------------------------------------------------------


class _Minor:
    def assess(self, user: Any) -> age.AgeAssurance:
        return age.AgeAssurance(is_minor=True, method="document", verified=True)


def test_the_default_backend_admits_it_cannot_tell(user: User) -> None:
    assessed = age.assess(user)
    assert assessed.is_minor is None and not assessed.verified


@override_settings(AGE_ASSURANCE_BACKEND=f"{__name__}._Minor")
def test_a_minor_cannot_grant_consent_without_a_guardian(user: User) -> None:
    from apps.privacy.models import ProcessingPurpose

    purpose = ProcessingPurpose.objects.create(
        code="news", name="News", description="d", lawful_basis="consent", retention_days=30
    )
    notice = PrivacyNotice.objects.create(
        version="1",
        document_url="https://example.com/n",
        checksum_sha256="c" * 64,
        effective_at=timezone.now(),
        active=True,
    )
    client = APIClient()
    client.force_authenticate(user)
    body = {"purpose": str(purpose.pk), "notice": str(notice.pk), "decision": "granted"}
    refused = client.post("/api/v1/privacy/consents/", body, format="json")
    assert refused.status_code == 400 and "guardian_confirmed" in json.dumps(refused.json())
    allowed = client.post(
        "/api/v1/privacy/consents/", {**body, "guardian_confirmed": True}, format="json"
    )
    assert allowed.status_code in (200, 201)


# --- production configuration and doctor -------------------------------------------------------


def test_production_needs_a_controller_and_a_dpo_channel() -> None:
    ok: dict[str, Any] = {
        "controller_name": "Acme Ltda",
        "dpo_email": "dpo@acme.test",
        "dpo_contact_url": "",
        "allow_undeclared": False,
    }
    validators.check_privacy_contacts(**ok)
    validators.check_privacy_contacts(
        **{**ok, "dpo_email": "", "dpo_contact_url": "https://x.test"}
    )
    for bad in ({"controller_name": ""}, {"dpo_email": ""}):
        with pytest.raises(ImproperlyConfigured):
            validators.check_privacy_contacts(**{**ok, **bad})
    validators.check_privacy_contacts(**{**ok, "controller_name": "", "allow_undeclared": True})


def test_doctor_reports_what_is_missing_in_the_privacy_setup() -> None:
    with override_settings(
        PRIVACY_CONTROLLER_NAME="", DPO_EMAIL="", DPO_CONTACT_URL="", DEBUG=False
    ):
        result = checks.check_privacy()
    assert result.status == "warn" and "PRIVACY_CONTROLLER_NAME" in result.detail
    assert "no active privacy notice" in result.detail
    PrivacyNotice.objects.create(
        version="1",
        document_url="https://example.com/n",
        checksum_sha256="c" * 64,
        effective_at=timezone.now(),
        active=True,
    )
    assert checks.check_privacy().status == "ok"


def test_platform_sub_processors_start_inactive_until_the_operator_confirms_them() -> None:
    vendors = SubProcessor.objects.all()
    assert vendors.count() >= 4 and not vendors.filter(active=True).exists()
    assert not [
        v for v in APIClient().get("/api/v1/privacy/transparency/").json()["sub_processors"]
    ]
    call_command("privacy_seed")  # idempotent
    assert SubProcessor.objects.count() == vendors.count()


def test_an_impact_assessment_can_be_recorded() -> None:
    row = ImpactAssessment.objects.create(
        title="Import of customer lists",
        processing_description="Upload and dedupe contacts",
        data_categories=["contact"],
        risks=[{"risk": "leak", "likelihood": "low", "impact": "high"}],
    )
    assert row.status == ImpactAssessment.Status.DRAFT and str(row) == "Import of customer lists"


# --- the words a data subject reads --------------------------------------------------------------


def test_every_message_exists_in_every_language_with_the_same_placeholders() -> None:
    import re

    english = messages.CATALOG["en"]
    for lang, catalog in messages.CATALOG.items():
        assert set(catalog) == set(english), lang
        for key, text in catalog.items():
            assert set(re.findall(r"{(\w+)}", text)) == set(re.findall(r"{(\w+)}", english[key])), (
                lang,
                key,
            )


@override_settings(PRIVACY_MAIL_LANGUAGE="pt-br")
def test_requests_are_answered_in_portuguese_when_configured(user: User) -> None:
    from django.core import mail

    from apps.privacy.models import DataSubjectRequest
    from apps.privacy.services import execute_request

    request = DataSubjectRequest.objects.create(
        requester=user,
        request_type=DataSubjectRequest.RequestType.CONFIRMATION,
        identity_verified_at=timezone.now(),
    )
    execute_request(request)
    request.refresh_from_db()
    assert "Tratamos seus dados" in request.response_summary
    assert any("concluída" in m.subject for m in mail.outbox)


@override_settings(PRIVACY_MAIL_LANGUAGE="klingon")
def test_an_unknown_language_falls_back_to_english() -> None:
    assert messages.say("completed.subject") == "Your request was completed"
