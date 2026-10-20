"""Serializer fields that cannot reference another tenant's rows.

A plain ``PrimaryKeyRelatedField(queryset=Model.objects.all())`` accepts any id, so a member of
organization A can attach their record to organization B's row (and, through the response,
confirm it exists). Use ``OrgScopedPrimaryKeyRelatedField`` for every foreign key a client can
write: the queryset is narrowed to the request's organization before the id is looked up, and
an id from elsewhere fails exactly like an id that does not exist.

    class CardSerializer(serializers.ModelSerializer):
        board = OrgScopedPrimaryKeyRelatedField(queryset=Board.objects.all())
"""

from __future__ import annotations

from typing import Any

from django.db.models import Model, QuerySet
from rest_framework import serializers


class OrgScopedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):  # type: ignore[type-arg]
    organization_field = "organization"

    def get_queryset(self) -> QuerySet[Model] | None:
        queryset = super().get_queryset()
        if queryset is None:
            return None
        request = self.context.get("request")
        organization = getattr(request, "organization", None)
        if organization is None:
            # No tenant on the request: refuse everything rather than fall back to all rows.
            return queryset.none()
        return queryset.filter(**{self.organization_field: organization})

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
