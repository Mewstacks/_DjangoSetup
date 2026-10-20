from __future__ import annotations

import uuid
from collections.abc import Collection, Iterable
from typing import Any, NoReturn, TypeVar

from django.core.exceptions import ValidationError
from django.db import models

ModelT = TypeVar("ModelT", bound=models.Model)


class AppendOnlyQuerySet(models.QuerySet[ModelT]):
    """Block ORM bulk operations that bypass model-level immutability checks."""

    @staticmethod
    def _reject() -> NoReturn:
        raise ValidationError("Append-only records cannot be changed in bulk.")

    def delete(self) -> NoReturn:
        self._reject()

    async def adelete(self) -> NoReturn:
        self._reject()

    def update(self, **kwargs: Any) -> NoReturn:
        self._reject()

    async def aupdate(self, **kwargs: Any) -> NoReturn:
        self._reject()

    def bulk_create(
        self,
        objs: Iterable[ModelT],
        batch_size: int | None = None,
        ignore_conflicts: bool = False,
        update_conflicts: bool = False,
        update_fields: Collection[str] | None = None,
        unique_fields: Collection[str] | None = None,
    ) -> NoReturn:
        self._reject()

    async def abulk_create(
        self,
        objs: Iterable[ModelT],
        batch_size: int | None = None,
        ignore_conflicts: bool = False,
        update_conflicts: bool = False,
        update_fields: Collection[str] | None = None,
        unique_fields: Collection[str] | None = None,
    ) -> NoReturn:
        self._reject()

    def bulk_update(
        self,
        objs: Iterable[ModelT],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> NoReturn:
        self._reject()

    async def abulk_update(
        self,
        objs: Iterable[ModelT],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> NoReturn:
        self._reject()


class UUIDTimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
