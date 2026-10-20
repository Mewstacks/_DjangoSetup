"""Re-encrypt every EncryptedTextField with the active key and the current scheme.

Run after adding a key to ``FIELD_ENCRYPTION_KEYS`` and switching
``FIELD_ENCRYPTION_ACTIVE_KEY_ID``; once it reports zero failures the old key can be removed.
Safe to repeat: each row is decrypted with whatever key wrote it and written back under the
active one. ``--dry-run`` only counts.
"""

from __future__ import annotations

from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.common.encryption import EncryptedTextField


class Command(BaseCommand):
    help = "Re-encrypt all encrypted columns with the active key (rotation / scheme upgrade)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        batch_size: int = options["batch_size"]
        rewritten = failed = 0
        for model in apps.get_models():
            fields = [f for f in model._meta.get_fields() if isinstance(f, EncryptedTextField)]
            if not fields:
                continue
            names = [f.attname for f in fields]
            queryset = model._base_manager.all().order_by("pk")
            for row in queryset.iterator(chunk_size=batch_size):
                try:
                    values = {name: getattr(row, name) for name in names}
                except Exception as exc:  # unreadable row: report, keep going
                    failed += 1
                    self.stderr.write(f"{model._meta.label} pk={row.pk}: {type(exc).__name__}")
                    continue
                if dry_run:
                    rewritten += 1
                    continue
                with transaction.atomic():
                    # update() bypasses save() overrides (append-only guards) on purpose: the
                    # logical content does not change, only its encryption envelope.
                    model._base_manager.filter(pk=row.pk).update(**values)
                rewritten += 1
        verb = "would rewrite" if dry_run else "rewrote"
        self.stdout.write(f"{verb} {rewritten} rows; {failed} unreadable.")
        if failed:
            raise SystemExit(1)
