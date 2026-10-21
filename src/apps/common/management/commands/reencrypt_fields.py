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

from apps.common.encryption import EncryptedTextField, decrypt_text, encrypt_text

# allauth keeps the TOTP seed and the recovery-code seed inside a JSON column, sealed by
# apps.accounts.adapters.MFAAdapter; the field scan above cannot see them.
MFA_SECRET_KEYS = {"totp": "secret", "recovery_codes": "seed"}


class Command(BaseCommand):
    help = "Re-encrypt all encrypted columns with the active key (rotation / scheme upgrade)."

    def _reseal_authenticators(self, dry_run: bool) -> tuple[int, int]:
        from allauth.mfa.models import Authenticator

        from apps.accounts.adapters import MFA_AAD

        rewritten = failed = 0
        for row in Authenticator.objects.filter(type__in=MFA_SECRET_KEYS).iterator():
            name = MFA_SECRET_KEYS[row.type]
            try:
                plain = decrypt_text(row.data[name], associated_data=MFA_AAD)
            except Exception as exc:
                failed += 1
                self.stderr.write(f"mfa.Authenticator pk={row.pk}: {type(exc).__name__}")
                continue
            if not dry_run:
                row.data[name] = encrypt_text(plain, associated_data=MFA_AAD)
                Authenticator.objects.filter(pk=row.pk).update(data=row.data)
            rewritten += 1
        return rewritten, failed

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
        mfa_rewritten, mfa_failed = self._reseal_authenticators(dry_run)
        rewritten += mfa_rewritten
        failed += mfa_failed
        verb = "would rewrite" if dry_run else "rewrote"
        self.stdout.write(f"{verb} {rewritten} rows; {failed} unreadable.")
        if failed:
            raise SystemExit(1)
