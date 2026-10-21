"""The stored file goes when its row goes, whichever way the row was deleted.

``services.remove`` used to delete the blob itself, so the two other ways a row disappears (a
data-subject erasure and the retention sweep both use ``QuerySet.delete``) left the file in the
bucket: personal data, outliving the person's request to be forgotten. Hooking the signal
covers every path, including the ones nobody has written yet.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.uploads.models import UploadedFile


@receiver(post_delete, sender=UploadedFile)
def remove_blob(sender: type[UploadedFile], instance: UploadedFile, **kwargs: Any) -> None:
    name, storage = instance.file.name, instance.file.storage
    if name:
        # Only if the database change commits: a rolled-back delete must keep its file.
        transaction.on_commit(lambda: storage.delete(name))
