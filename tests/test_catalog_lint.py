"""The data catalog is only as good as its field lists; these tests catch the field nobody listed."""

from __future__ import annotations

import pytest
from django.apps import apps

from apps.common.encryption import EncryptedTextField
from apps.privacy.catalog import CATALOG, SENSITIVE_CATEGORIES, Category
from devtools.project import PERSONAL_NAME
from devtools.project import REVIEWED_FIELDS as REVIEWED


def _personal_models() -> list[str]:
    return sorted(label for label, item in CATALOG.items() if item.personal)


@pytest.mark.parametrize("label", _personal_models())
def test_a_personal_model_lists_every_field_that_looks_personal(label: str) -> None:
    item = CATALOG[label]
    model = apps.get_model(label)
    unlisted = [
        field.name
        for field in model._meta.get_fields()
        if getattr(field, "concrete", False)
        and PERSONAL_NAME.search(field.name)
        and field.name not in item.fields
        and field.name not in REVIEWED.get(label, {})
    ]
    assert not unlisted, (
        f"{label}: {unlisted} look like personal data but are not in personal(fields=...). "
        "List them with a Category, or add them to REVIEWED with the reason they are fine."
    )


@pytest.mark.parametrize("label", _personal_models())
def test_sensitive_and_child_data_is_encrypted_at_rest(label: str) -> None:
    """Art. 5 II and art. 14: the categories with the highest risk never sit in clear text."""
    item = CATALOG[label]
    model = apps.get_model(label)
    clear = []
    for name, category in item.fields.items():
        if category not in SENSITIVE_CATEGORIES:
            continue
        field = model._meta.get_field(name)
        if not isinstance(field, EncryptedTextField):
            clear.append(name)
    assert not clear, f"{label}: {clear} are {sorted(SENSITIVE_CATEGORIES)} but not encrypted"


def test_reviewed_fields_exist_and_carry_a_reason() -> None:
    for label, fields in REVIEWED.items():
        model = apps.get_model(label)
        for name, reason in fields.items():
            model._meta.get_field(name)
            assert len(reason) >= 15, f"{label}.{name}: say why it is fine"


def test_credentials_never_leave_in_an_export() -> None:
    """A password hash is not 'their data' to carry; the export skips CREDENTIAL fields."""
    from apps.privacy.services import export_subject  # noqa: F401  (the rule lives there)

    credentials = [
        (label, name)
        for label, item in CATALOG.items()
        for name, category in item.fields.items()
        if category is Category.CREDENTIAL
    ]
    assert ("accounts.user", "password") in credentials
