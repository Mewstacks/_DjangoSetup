"""What the platform does when a person exercises a right (LGPD art. 18).

Every function here works on a ``DataSubject`` and the catalog, never on a particular app's
tables, so a new model is covered the moment it is classified. The flows (``workflows.py``) and
the local engine call the same functions; only *when* and *how durably* differs.

Nothing here decides legal questions. It applies the rules the catalog states, refuses while a
legal hold is active, and leaves anything it cannot decide to a human (``needs_review``).
"""

from __future__ import annotations

import io
import json
import secrets
import zipfile
from datetime import timedelta
from typing import Any

import structlog
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.signing import BadSignature, TimestampSigner
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.common.encryption import open_bytes, seal_bytes
from apps.common.exceptions import Conflict, Forbidden, NotFound
from apps.common.mail import send_safely
from apps.privacy.catalog import CATALOG, Category
from apps.privacy.models import (
    ConsentRecord,
    DataSubject,
    DataSubjectRequest,
    LegalHold,
    PrivacyNotice,
    PrivacyReminder,
    ProcessingPurpose,
    SubProcessor,
)

logger = structlog.get_logger("apps.privacy")
Status = DataSubjectRequest.Status
Type = DataSubjectRequest.RequestType
EXPORT_ROW_LIMIT = 10_000
EXPORT_SALT = "privacy-export-v1"
VERIFY_SALT = "privacy-verify-v1"


# --- identity ----------------------------------------------------------------------------


def subject_of(request: DataSubjectRequest) -> DataSubject:
    if request.subject_id:
        assert request.subject is not None
        return request.subject
    if request.requester_id:
        assert request.requester is not None
        subject = DataSubject.for_user(request.requester)
        request.subject = subject
        request.save(update_fields=["subject", "updated_at"])
        return subject
    raise NotFound("The request has no data subject.")


def anonymize_user(user: Any) -> None:
    """Make an account unusable and unidentifiable while keeping the row other tables point at."""
    user.email = f"anonymized-{user.pk}@anonymized.invalid"
    user.full_name = ""
    user.is_active = False
    user.is_staff = False
    user.is_superuser = False
    user.anonymized_at = timezone.now()
    user.set_unusable_password()
    user.save()
    user.groups.clear()
    user.user_permissions.clear()
    _drop_sessions(user)


def _drop_sessions(user: Any) -> int:
    """Delete this person's sessions. A scan: erasure is rare, and sessions hold no user index."""
    doomed = [
        session.pk
        for session in Session.objects.iterator(chunk_size=500)
        if str(session.get_decoded().get("_auth_user_id", "")) == str(user.pk)
    ]
    Session.objects.filter(pk__in=doomed).delete()
    return len(doomed)


# --- export (art. 18 II, V) ---------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, list | tuple | set):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def export_subject(subject: DataSubject) -> dict[str, Any]:
    """Everything the catalog says we hold about this person, in a machine-readable shape."""
    records: dict[str, Any] = {}
    for item in sorted(CATALOG.values(), key=lambda c: c.label):
        if not item.personal or item.resolver is None:
            continue
        # Credentials never leave in an export: a password hash is not "their data" to carry.
        names = [f for f, cat in item.fields.items() if cat is not Category.CREDENTIAL]
        rows = []
        for row in item.resolver(subject)[:EXPORT_ROW_LIMIT]:
            rows.append({"id": str(row.pk), **{n: _jsonable(getattr(row, n, None)) for n in names}})
        if rows:
            records[item.label] = rows
    return {
        "format": "saas-data-export/1",
        "generated_at": timezone.now().isoformat(),
        "subject": {"id": str(subject.pk), "email": subject.email},
        "records": records,
    }


def package_export(request: DataSubjectRequest) -> str:
    """Build the archive, seal it with the key ring and store it. Returns the storage name."""
    subject = subject_of(request)
    data = export_subject(subject)
    readme = (
        "Your data, as we hold it.\n\n"
        "data.json holds one list per kind of record (the key is the table). Passwords and "
        "other credentials are never included. This file was generated at "
        f"{data['generated_at']} for request {request.pk}.\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data.json", json.dumps(data, indent=2, ensure_ascii=False))
        archive.writestr("README.txt", readme)
    name = default_storage.save(
        f"privacy/exports/{request.pk}-{secrets.token_hex(4)}.zip.sealed",
        ContentFile(seal_bytes(buffer.getvalue(), purpose=b"saas/privacy-export/v1")),
    )
    request.export_name = name
    request.export_expires_at = timezone.now() + timedelta(days=settings.PRIVACY_EXPORT_TTL_DAYS)
    request.save(update_fields=["export_name", "export_expires_at", "updated_at"])
    return name


def export_token(request: DataSubjectRequest) -> str:
    return TimestampSigner(salt=EXPORT_SALT).sign(str(request.pk))


def read_export(token: str) -> tuple[DataSubjectRequest, bytes]:
    """The request and the decrypted archive for a valid, unexpired download token."""
    max_age = settings.PRIVACY_EXPORT_TTL_DAYS * 86400
    try:
        raw = TimestampSigner(salt=EXPORT_SALT).unsign(token, max_age=max_age)
    except BadSignature as error:
        raise NotFound("This download link is invalid or has expired.") from error
    request = DataSubjectRequest.objects.filter(pk=raw).first()
    if (
        request is None
        or not request.export_name
        or (request.export_expires_at and request.export_expires_at < timezone.now())
    ):
        raise NotFound("This download link is invalid or has expired.")
    with default_storage.open(request.export_name, "rb") as handle:
        return request, open_bytes(handle.read(), purpose=b"saas/privacy-export/v1")


# --- erasure, blocking (art. 18 IV, VI) ---------------------------------------------------


def erase_subject(subject: DataSubject) -> dict[str, Any]:
    """Apply every catalog rule to this person's data. Refuses while a legal hold is active."""
    if LegalHold.active_for(subject):
        raise Conflict("A legal hold requires this data to be kept.", code="legal_hold")
    report: dict[str, Any] = {}
    with transaction.atomic():
        user = subject.user
        for item in sorted(CATALOG.values(), key=lambda c: c.label):
            if not item.personal or item.resolver is None:
                continue
            rows = item.resolver(subject)
            count = rows.count()
            if not count:
                continue
            if item.on_erase == "keep":
                report[item.label] = {"kept": count, "reason": item.reason}
            elif item.model._meta.label_lower == "accounts.user":
                report[item.label] = {"anonymized": count}
            elif item.on_erase == "delete":
                rows.delete()
                report[item.label] = {"deleted": count}
            else:
                rows.update(**item.anonymize)
                report[item.label] = {"anonymized": count}
        # Free text the person wrote in their own requests goes; the requests themselves stay.
        DataSubjectRequest.objects.filter(subject=subject).update(details="", response_summary="")
        if user is not None:
            anonymize_user(user)
        subject.email = ""
        # Break the link a blind index would otherwise keep to the original address.
        subject.email_index = secrets.token_hex(32)
        subject.anonymized_at = timezone.now()
        subject.save()
    record_event(
        action="privacy.erased",
        metadata={"subject_models": len(report), "kept": sum("kept" in v for v in report.values())},
    )
    return report


def block_subject(subject: DataSubject) -> None:
    """Stop processing (art. 18 IV): deactivate the account and cut every credential."""
    from apps.apikeys.models import ApiKey

    with transaction.atomic():
        subject.blocked_at = timezone.now()
        subject.save(update_fields=["blocked_at", "updated_at"])
        user = subject.user
        if user is not None:
            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])
            ApiKey.objects.filter(user=user, revoked_at__isnull=True).update(
                revoked_at=timezone.now()
            )
            _drop_sessions(user)
            try:
                from oauth2_provider.models import get_access_token_model

                get_access_token_model().objects.filter(user=user).delete()
            except ImportError:
                pass
    record_event(action="privacy.blocked", metadata={"has_account": subject.user_id is not None})


# --- consent ------------------------------------------------------------------------------


def consent_state(user: Any) -> list[dict[str, Any]]:
    """The effective decision per consent purpose, with whether a newer notice needs a re-ask."""
    active = PrivacyNotice.objects.filter(active=True).first()
    latest: dict[Any, ConsentRecord] = {}
    for entry in ConsentRecord.objects.filter(user=user).order_by("recorded_at", "seq"):
        latest[entry.purpose_id] = entry
    state = []
    for purpose in ProcessingPurpose.objects.filter(
        lawful_basis=ProcessingPurpose.LawfulBasis.CONSENT, active=True
    ):
        record = latest.get(purpose.pk)
        granted = record is not None and record.decision == ConsentRecord.Decision.GRANTED
        state.append(
            {
                "purpose": purpose.code,
                "name": purpose.name,
                "decision": record.decision if record else None,
                "recorded_at": record.recorded_at if record else None,
                "notice_version": record.notice.version if record else None,
                "needs_renewal": bool(
                    granted
                    and active is not None
                    and record is not None
                    and record.notice_id != active.pk
                ),
            }
        )
    return state


def withdraw_all_consents(user: Any) -> int:
    """Withdraw every currently-granted consent. Returns how many were withdrawn."""
    count = 0
    for item in consent_state(user):
        if item["decision"] != ConsentRecord.Decision.GRANTED:
            continue
        purpose = ProcessingPurpose.objects.get(code=item["purpose"])
        last_record = (
            ConsentRecord.objects.filter(user=user, purpose=purpose).order_by("-seq").first()
        )
        assert last_record is not None
        last = last_record
        ConsentRecord.objects.create(
            user=user,
            purpose=purpose,
            notice=last.notice,
            decision=ConsentRecord.Decision.WITHDRAWN,
            source="data-subject-request",
        )
        count += 1
    return count


# --- executing a request ------------------------------------------------------------------

AUTOMATIC = {
    Type.ACCESS,
    Type.PORTABILITY,
    Type.CONFIRMATION,
    Type.DELETION,
    Type.ANONYMIZATION,
    Type.BLOCKING,
    Type.CONSENT_WITHDRAWAL,
    Type.SHARING_INFORMATION,
}


def _contact(request: DataSubjectRequest) -> str:
    if request.requester_id and request.requester and not request.requester.anonymized_at:
        return str(request.requester.email)
    if request.subject_id and request.subject and request.subject.email:
        return str(request.subject.email)
    return ""


def notify_requester(request: DataSubjectRequest, subject: str, body: str) -> None:
    address = _contact(request)
    if address:
        send_safely(subject, body, [address])


def notify_dpo(subject: str, body: str) -> None:
    if settings.DPO_EMAIL:
        send_safely(subject, body, [settings.DPO_EMAIL])
    else:
        logger.warning("dpo_email_missing", subject=subject)


def execute_request(request: DataSubjectRequest) -> dict[str, Any]:
    """Do what can be done without a person. Returns ``{"state": ..., ...}``.

    ``state`` is ``completed``, ``denied`` or ``needs_review``. A request that is not yet
    identity-verified is refused here - nothing is exported or erased for an unverified claim.
    """
    request.refresh_from_db()
    if request.is_terminal:
        return {"state": request.status}
    if request.identity_verified_at is None:
        raise Forbidden("Identity has not been verified.", code="identity_unverified")
    if request.status == Status.RECEIVED:
        request.transition_to(Status.IN_PROGRESS)
    if request.request_type not in AUTOMATIC:
        if request.status == Status.IN_PROGRESS:
            request.transition_to(Status.LEGAL_REVIEW)
        return {"state": "needs_review", "due_at": request.target_due_at.isoformat()}

    subject = subject_of(request)
    kind = request.request_type
    try:
        if kind in (Type.ACCESS, Type.PORTABILITY):
            package_export(request)
            summary = "Your export is ready; the download link was sent to you."
            notify_requester(
                request,
                "Your data export is ready",
                f"Download within {settings.PRIVACY_EXPORT_TTL_DAYS} days:\n"
                f"/api/v1/privacy/exports/{export_token(request)}/\n",
            )
        elif kind == Type.CONFIRMATION:
            purposes = list(
                ProcessingPurpose.objects.filter(active=True).values_list("name", flat=True)
            )
            summary = "We process your data for: " + ", ".join(purposes) + "."
        elif kind in (Type.DELETION, Type.ANONYMIZATION):
            report = erase_subject(subject)
            summary = (
                f"Done. {len(report)} kinds of record were reviewed; see your request history."
            )
        elif kind == Type.BLOCKING:
            block_subject(subject)
            summary = "Processing is blocked and your account was deactivated."
        elif kind == Type.CONSENT_WITHDRAWAL:
            count = withdraw_all_consents(subject.user) if subject.user else 0
            summary = f"{count} consent(s) withdrawn."
        else:  # SHARING_INFORMATION
            vendors = list(SubProcessor.objects.filter(active=True).values_list("name", flat=True))
            summary = "We share data with: " + (", ".join(vendors) or "no third parties") + "."
    except Conflict as error:
        request.transition_to(Status.DENIED, reason_code=error.code, summary=error.detail)
        notify_requester(request, "About your request", error.detail)
        return {"state": "denied", "reason": error.code}
    request.refresh_from_db()
    if not request.is_terminal:
        request.transition_to(Status.COMPLETED, summary=summary)
    if kind not in (Type.DELETION, Type.ANONYMIZATION):  # the address no longer exists after those
        notify_requester(request, "Your request was completed", summary)
    record_event(action="privacy.request_completed", metadata={"type": kind})
    return {"state": "completed"}


def finish_review(
    request: DataSubjectRequest, *, outcome: str, summary: str = "", reason_code: str = ""
) -> None:
    """A person has reviewed a request the platform could not decide. ``outcome`` is
    ``completed`` or ``denied``."""
    if request.status != Status.LEGAL_REVIEW:
        raise Conflict("Only a request under review can be finished.", code="not_in_review")
    if outcome == "denied":
        request.transition_to(Status.DENIED, summary=summary, reason_code=reason_code)
    else:
        request.transition_to(Status.COMPLETED, summary=summary)
    notify_requester(request, "Your request was answered", summary or "Your request was handled.")
    record_event(action="privacy.review_finished", metadata={"outcome": outcome})


# --- deadlines ----------------------------------------------------------------------------


def due_reminders(request: DataSubjectRequest, now: Any = None) -> list[str]:
    """Which reminder kinds apply to this request right now."""
    now = now or timezone.now()
    left = request.target_due_at - now
    kinds = []
    if left <= timedelta(days=5):
        kinds.append("due_in_5_days")
    if left <= timedelta(days=1):
        kinds.append("due_in_1_day")
    if left <= timedelta(0):
        kinds.append("overdue")
    return kinds


def send_reminders(request: DataSubjectRequest, now: Any = None) -> list[str]:
    """Send each due reminder once (the unique constraint makes re-running safe)."""
    sent = []
    for kind in due_reminders(request, now):
        _, created = PrivacyReminder.objects.get_or_create(request=request, kind=kind)
        if created:
            notify_dpo(
                f"[privacy] request {request.pk}: {kind.replace('_', ' ')}",
                f"Request {request.pk} ({request.request_type}) is {request.status}; "
                f"due {request.target_due_at:%Y-%m-%d}.",
            )
            sent.append(kind)
    return sent
