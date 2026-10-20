from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.flags import services
from apps.flags.models import Flag, FlagRule
from apps.organizations.models import Organization

pytestmark = pytest.mark.django_db


def test_unknown_flag_is_off_and_default_applies() -> None:
    assert services.is_enabled("nope") is False
    Flag.objects.create(key="beta", default_enabled=True)
    assert services.is_enabled("beta") is True


def test_precedence_user_then_org_then_percentage(organization: Organization, user) -> None:  # type: ignore[no-untyped-def]
    flag = Flag.objects.create(key="beta", default_enabled=False)
    FlagRule.objects.create(flag=flag, organization=organization, enabled=True)
    assert services.is_enabled("beta", organization=organization)
    FlagRule.objects.create(flag=flag, user=user, enabled=False)
    assert not services.is_enabled("beta", organization=organization, user=user)


def test_percentage_is_stable_and_bounded(organization: Organization) -> None:
    flag = Flag.objects.create(key="gradual")
    FlagRule.objects.create(flag=flag, percentage=100)
    assert services.is_enabled("gradual", organization=organization)
    FlagRule.objects.filter(flag=flag).update(percentage=0)
    services.invalidate()
    assert not services.is_enabled("gradual", organization=organization)
    with pytest.raises(IntegrityError), transaction.atomic():
        FlagRule.objects.create(flag=flag, percentage=101)


def test_rule_needs_exactly_one_target(organization: Organization) -> None:
    flag = Flag.objects.create(key="x")
    with pytest.raises(ValidationError):
        FlagRule(flag=flag).full_clean()


def test_changes_invalidate_the_cache() -> None:
    flag = Flag.objects.create(key="live")
    assert not services.is_enabled("live")
    Flag.objects.filter(pk=flag.pk).first()
    flag.default_enabled = True
    flag.save()
    assert services.is_enabled("live")


def test_settings_validate_type_and_scope_to_org(organization: Organization) -> None:
    from apps.common.exceptions import Invalid

    assert services.get_setting("notes.max_title_length") == 200
    services.set_setting("notes.max_title_length", 50)
    services.set_setting("notes.max_title_length", 80, organization=organization)
    assert services.get_setting("notes.max_title_length") == 50
    assert services.get_setting("notes.max_title_length", organization=organization) == 80
    with pytest.raises(Invalid):
        services.set_setting("notes.max_title_length", "big")
    with pytest.raises(Invalid):
        services.set_setting("notes.max_title_length", True)
    with pytest.raises(KeyError):
        services.get_setting("undeclared")


def test_actions_expose_evaluation(org_client) -> None:  # type: ignore[no-untyped-def]
    Flag.objects.create(key="on", default_enabled=True)
    response = org_client.post("/api/v1/actions/flags.evaluate/", {}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["flags"] == {"on": True}
