"""Public privacy endpoints: transparency, cookie configuration, requests without an account.

Everything here answers anonymous callers, so the rules are strict: throttled by client address
and by e-mail, identical responses whether or not an address is known (no enumeration), and a
request is not acted on until the e-mail is confirmed.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.signing import BadSignature, TimestampSigner
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_event
from apps.common.exceptions import Invalid, NotFound, Unavailable
from apps.common.mail import send_safely
from apps.common.network import client_ip_bucket
from apps.common.throttling import IPAnonRateThrottle, IPScopedRateThrottle
from apps.privacy.lifecycle import mark_verified, start_dsar
from apps.privacy.models import (
    DataSubject,
    DataSubjectRequest,
    PrivacyNotice,
    ProcessingPurpose,
    SubProcessor,
)
from apps.privacy.services import VERIFY_SALT, read_export

VERIFY_MAX_AGE = 48 * 3600
PER_EMAIL_PER_DAY = 3


class PublicBase(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]
    throttle_classes = [IPAnonRateThrottle]


class TransparencyView(PublicBase):
    """Who is responsible, who to ask, what we process and who else sees it (art. 9, 41)."""

    @extend_schema(
        responses=inline_serializer("Transparency", {"controller": serializers.DictField()})
    )
    def get(self, request: Request) -> Response:
        notice = PrivacyNotice.objects.filter(active=True).first()
        return Response(
            {
                "controller": {
                    "name": settings.PRIVACY_CONTROLLER_NAME,
                    "id": settings.PRIVACY_CONTROLLER_ID,
                },
                "dpo": {
                    "name": settings.DPO_NAME,
                    "email": settings.DPO_EMAIL,
                    "contact_url": settings.DPO_CONTACT_URL,
                },
                "notice": (
                    {
                        "id": str(notice.pk),
                        "version": notice.version,
                        "url": notice.document_url,
                        "checksum_sha256": notice.checksum_sha256,
                        "effective_at": notice.effective_at,
                    }
                    if notice
                    else None
                ),
                "purposes": [
                    {
                        "code": p.code,
                        "name": p.name,
                        "description": p.description,
                        "lawful_basis": p.lawful_basis,
                        "data_categories": p.data_categories,
                        "retention_days": p.retention_days,
                    }
                    for p in ProcessingPurpose.objects.filter(active=True)
                ],
                "sub_processors": [
                    {
                        "name": s.name,
                        "purpose": s.purpose,
                        "country": s.country,
                        "transfer_mechanism": s.transfer_mechanism,
                    }
                    for s in SubProcessor.objects.filter(active=True)
                ],
            }
        )


class CookieConfigView(PublicBase):
    """What a consent banner needs: categories, their purposes and the notice to reference."""

    @extend_schema(
        responses=inline_serializer("CookieConfig", {"categories": serializers.ListField()})
    )
    def get(self, request: Request) -> Response:
        notice = PrivacyNotice.objects.filter(active=True).first()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for purpose in ProcessingPurpose.objects.filter(active=True).exclude(cookie_category=""):
            grouped.setdefault(purpose.cookie_category, []).append(
                {"code": purpose.code, "name": purpose.name, "description": purpose.description}
            )
        return Response(
            {
                "notice_id": str(notice.pk) if notice else None,
                "categories": [
                    {
                        "category": name,
                        "required": name == ProcessingPurpose.CookieCategory.NECESSARY,
                        "purposes": items,
                    }
                    for name, items in sorted(grouped.items())
                ],
            }
        )


class PublicRequestSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField()
    request_type = serializers.ChoiceField(choices=DataSubjectRequest.RequestType.choices)
    details = serializers.CharField(required=False, allow_blank=True, max_length=10_000)


class PublicRequestView(PublicBase):
    """Ask to exercise a right without an account. Always answers the same thing."""

    throttle_classes = [IPAnonRateThrottle, IPScopedRateThrottle]
    throttle_scope = "privacy_public"

    @extend_schema(request=PublicRequestSerializer, responses={202: None})
    def post(self, request: Request) -> Response:
        if not settings.PRIVACY_PUBLIC_REQUESTS:
            raise NotFound("Not available.")
        serializer = PublicRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        subject = DataSubject.for_email(data["email"])
        # Per-address cap so the form cannot be used to mail-bomb a third party.
        key = f"privacy:public:{subject.email_index}:{timezone.now():%Y%m%d}"
        cache.add(key, 0, 90_000)
        if int(cache.incr(key)) <= PER_EMAIL_PER_DAY:
            created = DataSubjectRequest.objects.create(
                subject=subject,
                request_type=data["request_type"],
                details=data.get("details", ""),
                status=DataSubjectRequest.Status.VERIFYING,
            )
            token = TimestampSigner(salt=VERIFY_SALT).sign(str(created.pk))
            send_safely(
                "Confirm your request",
                f"Confirm that you made this request: {token}\n",
                [data["email"]],
            )
            record_event(
                action="privacy.public_request.received",
                request=request._request,
                metadata={"request_type": data["request_type"]},
            )
        # Same answer whether the address was new, known or over its cap.
        return Response({"status": "check_your_email"}, status=status.HTTP_202_ACCEPTED)


class PublicVerifySerializer(serializers.Serializer[dict[str, Any]]):
    token = serializers.CharField(max_length=300)


class PublicVerifyView(PublicBase):
    throttle_classes = [IPAnonRateThrottle, IPScopedRateThrottle]
    throttle_scope = "privacy_public"

    @extend_schema(request=PublicVerifySerializer, responses={200: None})
    def post(self, request: Request) -> Response:
        serializer = PublicVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            raw = TimestampSigner(salt=VERIFY_SALT).unsign(
                serializer.validated_data["token"], max_age=VERIFY_MAX_AGE
            )
        except BadSignature as error:
            raise Invalid("This confirmation link is invalid or has expired.") from error
        pending = (
            DataSubjectRequest.objects.filter(pk=raw, status=DataSubjectRequest.Status.VERIFYING)
            .select_related("subject")
            .first()
        )
        if pending is None:
            raise Invalid("This confirmation link is invalid or has expired.")
        subject = pending.subject
        assert subject is not None
        subject.verified_at = subject.verified_at or timezone.now()
        subject.save(update_fields=["verified_at", "updated_at"])
        pending.transition_to(DataSubjectRequest.Status.IN_PROGRESS)
        mark_verified(pending)
        if not start_dsar(pending):
            raise Unavailable("We recorded your request and will process it shortly.")
        return Response({"status": "verified"})


class ExportDownloadView(PublicBase):
    """The archive for a valid link. Possession of the link, delivered to the verified address,
    is the credential; an account holder must additionally be signed in as the requester."""

    authentication_classes: list[type] = []

    @extend_schema(responses={200: bytes})
    def get(self, request: Request, token: str) -> HttpResponse:
        privacy_request, archive = read_export(token)
        django_request = request._request
        if privacy_request.requester_id:
            user = getattr(django_request, "user", None)
            if not (user and user.is_authenticated and user.pk == privacy_request.requester_id):
                raise NotFound("This download link is invalid or has expired.")
        record_event(action="privacy.export_downloaded", request=django_request)
        response = HttpResponse(archive, content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="my-data.zip"'
        response["Cache-Control"] = "no-store"
        return response


__all__ = [
    "CookieConfigView",
    "ExportDownloadView",
    "PublicRequestView",
    "PublicVerifyView",
    "TransparencyView",
    "client_ip_bucket",
]
