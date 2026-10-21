"""Properties every action must have, checked for the whole registry.

Add an action and these run against it with no test written: a missing scope, a read-only role,
an unlisted channel and bad input are all refused the way the platform promises. The tests that
need real data (cross-tenant access, idempotent replay) live next to the action; the ones here
need none, which is why they can be generic.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from apps.actions import journal, registry
from apps.actions.context import build_context
from apps.actions.registry import CHANNELS, REGISTRY, ActionSpec
from apps.actions.runtime import _parse, invoke
from apps.common.exceptions import Forbidden, Invalid, NotFound
from apps.organizations.models import Membership, Organization

NAMES = sorted(REGISTRY)
SENTINEL = "SENTINEL-4f9a2c-must-not-be-echoed"
SECRETISH = re.compile(r"password|secret|token|api_?key|authorization|private_?key", re.I)


def _spec(name: str) -> ActionSpec:
    return REGISTRY[name]


def test_the_registry_is_not_empty() -> None:
    assert len(NAMES) >= 16


@pytest.mark.parametrize("name", NAMES)
def test_an_unlisted_channel_cannot_see_the_action(
    name: str, user: Any, organization: Organization, membership: Membership
) -> None:
    spec = _spec(name)
    unlisted = sorted(CHANNELS - spec.channels)
    if not unlisted:
        pytest.skip("listed on every channel")
    ctx = build_context(
        user=user, organization=organization, channel=unlisted[0], scopes=frozenset({"*"})
    )
    with pytest.raises(NotFound):  # 404, not 403: do not confirm the action exists
        invoke(name, ctx, {})


@pytest.mark.parametrize("name", NAMES)
def test_a_credential_without_the_scope_is_refused(
    name: str, user: Any, organization: Organization, membership: Membership
) -> None:
    spec = _spec(name)
    channel = sorted(spec.channels)[0]
    ctx = build_context(
        user=user,
        organization=organization,
        channel=channel,
        scopes=frozenset({"unrelated:read"}),
    )
    with pytest.raises(Forbidden) as caught:
        invoke(name, ctx, {})
    assert caught.value.code == "missing_scope"


@pytest.mark.parametrize("name", [n for n in NAMES if _spec(n).write and _spec(n).roles is None])
def test_read_only_roles_cannot_run_a_write_action(
    name: str, user: Any, organization: Organization
) -> None:
    from apps.accounts.models import User

    for role in (Membership.Role.AUDITOR, Membership.Role.BILLING):
        person = User.objects.create_user(email=f"{role}@example.com", password="x" * 14)
        Membership.objects.create(organization=organization, user=person, role=role)
        ctx = build_context(
            user=person,
            organization=organization,
            channel=sorted(_spec(name).channels)[0],
            scopes=frozenset({"*"}),
        )
        with pytest.raises(Forbidden) as caught:
            invoke(name, ctx, {})
        assert caught.value.code == "read_only_role", role


@pytest.mark.parametrize("name", [n for n in NAMES if _spec(n).input_model is not None])
def test_invalid_input_is_refused_without_echoing_it(name: str) -> None:
    spec = _spec(name)
    assert spec.input_model is not None
    payload = {field: {"leak": SENTINEL} for field in spec.input_model.model_fields}
    payload["not_a_field_at_all"] = SENTINEL
    try:
        _parse(spec, payload)
    except Invalid as refused:
        assert SENTINEL not in json.dumps(refused.payload(), default=str)
        assert SENTINEL not in str(refused.detail)
    else:
        pytest.skip("every field accepts an object, so nothing to refuse")


@pytest.mark.parametrize("name", NAMES)
def test_the_description_is_written_for_the_model_that_reads_it(name: str) -> None:
    spec = _spec(name)
    assert len(spec.description) >= 20, "the docstring is the tool description an agent reads"
    assert not re.search(r"\b(TODO|FIXME|XXX)\b", spec.description)
    assert spec.title


@pytest.mark.parametrize("name", NAMES)
def test_outputs_never_carry_a_field_named_like_a_secret(name: str) -> None:
    spec = _spec(name)
    if spec.output_model is None:
        pytest.skip("no output")
    secretish = [f for f in spec.output_model.model_fields if SECRETISH.search(f)]
    assert not secretish, f"{name} returns {secretish}: an action's output is logged and audited"


@pytest.mark.parametrize("name", [n for n in NAMES if _spec(n).write])
def test_every_write_action_decided_whether_it_can_be_undone(name: str) -> None:
    spec = _spec(name)
    assert spec.undoable is not None
    if isinstance(spec.undoable, str):
        assert len(spec.undoable) >= 15, "say why, in a sentence"
    else:
        assert spec.undoable is True
        assert journal._HANDLERS, "undoable=True but no undo handler is registered (undo.py)"


@pytest.mark.parametrize("name", [n for n in NAMES if not _spec(n).write])
def test_read_actions_are_never_marked_undoable_or_destructive(name: str) -> None:
    spec = _spec(name)
    assert spec.undoable is None and not spec.destructive and not spec.audit


def test_a_write_action_without_an_undo_decision_fails_at_import() -> None:
    def tmp(ctx: Any) -> None:
        """A write action that forgot to decide."""

    with pytest.raises(ValueError, match="undoable"):
        registry.action("tmp.undecided", write=True)(tmp)
    with pytest.raises(ValueError, match="reason"):
        registry.action("tmp.false", write=True, undoable=False)(tmp)  # type: ignore[arg-type]
    assert not [n for n in registry.REGISTRY if n.startswith("tmp.")]


def test_undo_modules_are_discovered_without_a_manual_import() -> None:
    from apps.actions.registry import DISCOVERED

    assert "undo" in DISCOVERED
    assert ("examples.note", "create") in journal._HANDLERS or any(
        key[1] == "create" for key in journal._HANDLERS
    )
