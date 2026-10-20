from __future__ import annotations

from types import SimpleNamespace

import pytest
from rest_framework import serializers

from apps.examples.models import Note
from apps.organizations.fields import OrgScopedPrimaryKeyRelatedField
from apps.organizations.models import Organization

pytestmark = pytest.mark.django_db


class Link(serializers.Serializer):  # type: ignore[type-arg]
    note = OrgScopedPrimaryKeyRelatedField(queryset=Note.objects.all())


def validate(organization: Organization | None, pk: object) -> serializers.Serializer:  # type: ignore[type-arg]
    request = SimpleNamespace(organization=organization)
    serializer = Link(data={"note": str(pk)}, context={"request": request})
    serializer.is_valid()
    return serializer


def test_own_rows_resolve_and_foreign_rows_look_nonexistent(organization: Organization) -> None:
    other_organization = Organization.objects.create(name="Globex", slug="globex")
    mine = Note.objects.create(organization=organization, title="mine")
    theirs = Note.objects.create(organization=other_organization, title="theirs")

    ok = validate(organization, mine.pk)
    assert not ok.errors and ok.validated_data["note"] == mine

    foreign = validate(organization, theirs.pk)
    missing = validate(organization, "00000000-0000-0000-0000-000000000000")
    codes = [e.code for e in foreign.errors["note"]]
    assert codes == [e.code for e in missing.errors["note"]] == ["does_not_exist"]


def test_without_a_tenant_nothing_resolves(organization: Organization) -> None:
    mine = Note.objects.create(organization=organization, title="mine")
    assert validate(None, mine.pk).errors
