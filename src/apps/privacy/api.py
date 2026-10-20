from __future__ import annotations

import uuid
from typing import Any, cast

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from rest_framework import serializers, viewsets

from apps.accounts.models import User
from apps.audit.services import record_event
from apps.common.encryption import PREFIX
from apps.common.throttling import IPUserRateThrottle
from apps.privacy.models import (
    ConsentRecord,
    DataSubjectRequest,
    PrivacyNotice,
    ProcessingPurpose,
)


class PrivacyThrottle(IPUserRateThrottle):
    scope = "privacy"


class ProcessingPurposeSerializer(serializers.ModelSerializer[ProcessingPurpose]):
    class Meta:
        model = ProcessingPurpose
        fields = (
            "id",
            "code",
            "name",
            "description",
            "lawful_basis",
            "data_categories",
            "retention_days",
        )


class ProcessingPurposeViewSet(viewsets.ReadOnlyModelViewSet[ProcessingPurpose]):
    serializer_class = ProcessingPurposeSerializer
    queryset = ProcessingPurpose.objects.filter(active=True)
    lookup_value_converter = "uuid"


class ConsentSerializer(serializers.ModelSerializer[ConsentRecord]):
    idempotency_key = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = ConsentRecord
        fields = (
            "id",
            "idempotency_key",
            "purpose",
            "notice",
            "decision",
            "recorded_at",
        )
        read_only_fields = ("id", "recorded_at")

    def validate_purpose(self, purpose: ProcessingPurpose) -> ProcessingPurpose:
        if not purpose.active:
            raise serializers.ValidationError("This processing purpose is inactive.")
        if purpose.lawful_basis != ProcessingPurpose.LawfulBasis.CONSENT:
            raise serializers.ValidationError(
                "This purpose does not use consent as its lawful basis."
            )
        return purpose

    def validate_notice(self, notice: PrivacyNotice) -> PrivacyNotice:
        if not notice.active:
            raise serializers.ValidationError("This privacy notice is inactive.")
        return notice

    def _existing_for_key(self, key: uuid.UUID) -> ConsentRecord | None:
        return ConsentRecord.objects.filter(idempotency_key=key).first()

    def _reconcile(
        self,
        existing: ConsentRecord,
        user: User,
        validated_data: dict[str, Any],
    ) -> ConsentRecord:
        same_event = (
            existing.user_id == user.id
            and existing.purpose_id == validated_data["purpose"].id
            and existing.notice_id == validated_data["notice"].id
            and existing.decision == validated_data["decision"]
        )
        if not same_event:
            raise serializers.ValidationError("Idempotency key was already used.")
        return existing

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> ConsentRecord:
        key = validated_data.pop("idempotency_key", uuid.uuid4())
        user = cast(User, self.context["request"].user)
        existing = self._existing_for_key(key)
        if existing is not None:
            return self._reconcile(existing, user, validated_data)
        try:
            with transaction.atomic():
                record = ConsentRecord.objects.create(
                    idempotency_key=key,
                    user=user,
                    source="api",
                    **validated_data,
                )
        except (IntegrityError, DjangoValidationError):
            # A concurrent request committed the same idempotency_key between our lookup and
            # our insert (TOCTOU). The duplicate can surface either as a database
            # IntegrityError or, via ConsentRecord.save()'s full_clean(), as a Django
            # ValidationError. The inner atomic() savepoint rolled the failed insert back
            # without poisoning the outer transaction, so converge on the winning record if
            # one now exists; otherwise the error was not a duplicate and must propagate.
            existing = self._existing_for_key(key)
            if existing is None:
                raise
            return self._reconcile(existing, user, validated_data)
        record_event(
            action=f"privacy.consent.{record.decision}",
            actor=user,
            target=record,
            metadata={"purpose_code": record.purpose.code},
        )
        return record


class ConsentViewSet(viewsets.ModelViewSet[ConsentRecord]):
    queryset = ConsentRecord.objects.none()
    serializer_class = ConsentSerializer
    throttle_classes = [PrivacyThrottle]
    http_method_names = ["get", "post", "head", "options"]
    lookup_value_converter = "uuid"

    def get_queryset(self) -> QuerySet[ConsentRecord]:
        if getattr(self, "swagger_fake_view", False):
            return ConsentRecord.objects.none()
        user = cast(User, self.request.user)
        return ConsentRecord.objects.filter(user=user).select_related(
            "purpose",
            "notice",
        )


class DataSubjectRequestSerializer(serializers.ModelSerializer[DataSubjectRequest]):
    details = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        max_length=10_000,
    )

    class Meta:
        model = DataSubjectRequest
        fields = (
            "id",
            "request_type",
            "status",
            "details",
            "response_summary",
            "target_due_at",
            "completed_at",
            "denial_reason_code",
            "created_at",
        )
        read_only_fields = (
            "id",
            "status",
            "response_summary",
            "target_due_at",
            "completed_at",
            "denial_reason_code",
            "created_at",
        )

    def validate_details(self, value: str) -> str:
        # Defence in depth for the encrypted column: a user must never be able to submit a
        # value that looks like an internal ciphertext token (see apps.common.encryption).
        if value.startswith(f"{PREFIX}:"):
            raise serializers.ValidationError(
                "Details must not begin with the internal encryption marker."
            )
        return value

    def create(self, validated_data: dict[str, Any]) -> DataSubjectRequest:
        user = cast(User, self.context["request"].user)
        privacy_request = DataSubjectRequest.objects.create(
            requester=user,
            **validated_data,
        )
        record_event(
            action="privacy.subject_request.received",
            actor=user,
            target=privacy_request,
            metadata={"request_type": privacy_request.request_type},
        )
        return privacy_request


class DataSubjectRequestViewSet(viewsets.ModelViewSet[DataSubjectRequest]):
    queryset = DataSubjectRequest.objects.none()
    serializer_class = DataSubjectRequestSerializer
    throttle_classes = [PrivacyThrottle]
    http_method_names = ["get", "post", "head", "options"]
    lookup_value_converter = "uuid"

    def get_queryset(self) -> QuerySet[DataSubjectRequest]:
        if getattr(self, "swagger_fake_view", False):
            return DataSubjectRequest.objects.none()
        user = cast(User, self.request.user)
        return DataSubjectRequest.objects.filter(requester=user)
