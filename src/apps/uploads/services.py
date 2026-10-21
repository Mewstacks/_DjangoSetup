from __future__ import annotations

import hashlib
import logging
from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile as DjangoUploadedFile
from django.db import transaction

from apps.audit.services import record_event
from apps.common.exceptions import Invalid, Unavailable
from apps.organizations import quotas
from apps.organizations.models import Organization
from apps.uploads import policy, scan
from apps.uploads.models import UploadedFile

logger = logging.getLogger(__name__)


class ScannerDown(Unavailable):
    code = "scanner_unavailable"


class Infected(Invalid):
    code = "file_rejected"


def store(
    upload: DjangoUploadedFile[Any], *, organization: Organization, user: Any, request: Any = None
) -> UploadedFile:
    upload.seek(0)
    data = upload.read(int(settings.UPLOAD_MAX_BYTES) + 1)
    quotas.uploads(organization, size=len(data))
    verdict = policy.inspect(upload.name or "", data[: policy.SNIFF_BYTES], data, len(data))
    status = UploadedFile.ScanStatus.SKIPPED
    if scan.configured():
        try:
            result = scan.scan(data)
        except scan.ScanUnavailable as exc:
            logger.warning("upload.scan_unavailable", extra={"error": str(exc)})
            if settings.UPLOAD_CLAMAV_REQUIRED:
                raise ScannerDown("Files cannot be checked right now.") from exc
        else:
            if result != "clean":
                record_event(
                    action="upload.rejected",
                    actor=user,
                    organization=organization,
                    metadata={"reason": "infected"},
                    request=request,
                )
                raise Infected("The file was rejected.")
            status = UploadedFile.ScanStatus.CLEAN
    with transaction.atomic():
        row = UploadedFile(
            organization=organization,
            uploaded_by=user,
            original_name=verdict.display_name,
            content_type=verdict.content_type,
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            scan_status=status,
        )
        row.file.save("blob", ContentFile(data), save=False)
        row.save()
        record_event(
            action="upload.created",
            actor=user,
            organization=organization,
            target=row,
            metadata={"size": row.size, "content_type": row.content_type},
            request=request,
        )
    return row


def remove(row: UploadedFile, *, user: Any, request: Any = None) -> None:
    organization = row.organization
    with transaction.atomic():
        record_event(
            action="upload.deleted",
            actor=user,
            organization=organization,
            target=row,
            request=request,
        )
        row.delete()  # the post_delete hook in apps.uploads.signals removes the blob on commit
