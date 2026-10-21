"""Flows without a Temporal server: the local engine, jobs, the codec, the task backend, rules."""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient
from temporalio.api.common.v1 import Payload

import flow_fixtures  # noqa: F401  (registers the test flows)
from apps.accounts.models import User
from apps.common.encryption import clear_key_cache
from apps.common.exceptions import NotFound
from apps.examples.models import Note
from apps.flows.codec import EncryptionCodec
from apps.flows.declare import FLOWS, JOBS, job
from apps.flows.engine import FlowsDisabled, LocalEngine, capabilities, get_engine
from apps.flows.jobs_runtime import execute_job
from apps.flows.models import FlowRun
from apps.organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db


def test_the_local_engine_is_the_default_and_says_what_it_cannot_do() -> None:
    assert get_engine().name == "local"
    missing = {row["capability"] for row in capabilities() if row["local"] is False}
    assert "Signals to a running flow" in missing
    assert "Durable timers and sleeps (hours to months)" in missing


def test_a_portable_flow_runs_inline_and_is_recorded(
    user: User, organization: Organization, membership: Membership
) -> None:
    run = LocalEngine().start(
        "test.greet",
        {"title": "inline", "secret": "s3"},
        organization=organization,
        actor=user,
    )
    assert run.status == FlowRun.Status.COMPLETED and run.engine == "local"
    assert Note.objects.get(title="inline").body == "s3"
    assert json.loads(run.result_json)["note_id"] == str(Note.objects.get().pk)
    assert run.started_at and run.finished_at
    # The record itself is encrypted at rest, like every other place a payload is kept.
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT input_json, result_json FROM flows_flowrun")
        assert all(v.startswith("enc:v2:") for v in cursor.fetchone())


def test_a_failing_local_flow_is_a_recorded_outcome_not_a_crash() -> None:
    run = LocalEngine().start("test.local_only_boom", {})
    assert run.status == FlowRun.Status.FAILED and "boom" in run.error


def test_temporal_only_features_refuse_loudly_instead_of_pretending() -> None:
    engine = LocalEngine()
    with pytest.raises(FlowsDisabled) as needs:
        engine.start("test.approval", {})
    assert needs.value.code == "flow_needs_temporal"
    run = FlowRun.objects.create(flow="x", engine="local")
    for call in (lambda: engine.signal(run, "approve"), lambda: engine.cancel(run)):
        with pytest.raises(FlowsDisabled):
            call()
    from datetime import timedelta

    with pytest.raises(FlowsDisabled) as delayed:
        engine.start("test.local_only_boom", {}, start_delay=timedelta(hours=1))
    assert delayed.value.code == "delay_needs_temporal"
    with pytest.raises(NotFound):
        engine.start("no.such.flow", {})


def test_flow_input_is_validated_against_its_model() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LocalEngine().start("test.greet", {"secret": "x"}, organization=None)


# --- actions over flows ---------------------------------------------------------------------


def test_flows_are_started_and_followed_through_actions(
    org_client: APIClient, user: User, organization: Organization
) -> None:
    catalog = org_client.post("/api/v1/actions/flows.catalog/", {}, format="json")
    assert catalog.status_code == 200 and catalog.data["engine"] == "local"
    names = {f["name"] for f in catalog.data["flows"]}
    assert {"test.greet", "platform.job"} <= names

    started = org_client.post(
        "/api/v1/actions/flows.start/",
        {
            "flow": "test.greet",
            "input": {"title": "via api"},
        },
        format="json",
    )
    assert started.status_code == 200 and started.data["status"] == "completed"
    status = org_client.post(
        "/api/v1/actions/flows.status/", {"id": started.data["id"]}, format="json"
    )
    assert status.data["status"] == "completed"
    listed = org_client.post("/api/v1/actions/flows.runs/", {}, format="json")
    assert [r["id"] for r in listed.data["items"]] == [started.data["id"]]


def test_only_flows_marked_startable_can_be_started_over_the_api(org_client: APIClient) -> None:
    for flow in ("platform.job", "test.approval", "nope.nope"):
        response = org_client.post(
            "/api/v1/actions/flows.start/", {"flow": flow, "input": {}}, format="json"
        )
        assert response.status_code == 404, flow


def test_runs_of_another_organization_are_invisible(
    org_client: APIClient, other_org_client: APIClient, user: User, organization: Organization
) -> None:
    run = LocalEngine().start(
        "test.greet",
        {"title": "mine"},
        organization=organization,
        actor=user,
    )
    assert (
        other_org_client.post(
            "/api/v1/actions/flows.status/", {"id": str(run.pk)}, format="json"
        ).status_code
        == 404
    )
    assert (
        other_org_client.post("/api/v1/actions/flows.runs/", {}, format="json").data["items"] == []
    )


# --- jobs --------------------------------------------------------------------------------


def test_jobs_run_by_name_and_unknown_jobs_are_not_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert "deleted" in execute_job("maintenance.prune_idempotency")
    with pytest.raises(NotFound):
        execute_job("nope")
    call_command("run_job", "maintenance.close_idle_runs")
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1]) == {"closed": 0}
    call_command("run_job", "--list")
    assert "maintenance.purge_journal" in capsys.readouterr().out


def test_every_scheduled_job_has_a_valid_five_field_cron() -> None:
    assert JOBS
    for spec in JOBS.values():
        if spec.schedule:
            assert len(spec.schedule.split()) == 5, spec.name


def test_duplicate_declarations_fail_at_import_time() -> None:
    with pytest.raises(ValueError, match="twice"):
        job("maintenance.purge_journal")(lambda: None)


def test_a_job_can_also_run_as_a_local_flow() -> None:
    run = LocalEngine().start("platform.job", {"name": "maintenance.close_idle_runs"})
    assert run.status == FlowRun.Status.COMPLETED


# --- codec ---------------------------------------------------------------------------------

KEY = {"k1": b"1" * 32, "k2": b"2" * 32}


def _roundtrip(codec: EncryptionCodec, data: bytes) -> tuple[Payload, Payload]:
    plain = Payload(metadata={"encoding": b"json/plain"}, data=data)
    sealed = asyncio.run(codec.encode([plain]))[0]
    opened = asyncio.run(codec.decode([sealed]))[0]
    assert opened == plain
    return plain, sealed


def test_codec_seals_payloads_and_authenticates_them() -> None:
    codec = EncryptionCodec(KEY, "k1")
    _, sealed = _roundtrip(codec, b'{"cpf": "123.456.789-09"}')
    assert b"123.456" not in sealed.data and b"cpf" not in sealed.data
    assert sealed.metadata["platform-key-id"] == b"k1"
    tampered = Payload(metadata=dict(sealed.metadata), data=sealed.data[:-1] + b"\x00")
    with pytest.raises(ValueError, match="authentication"):
        asyncio.run(codec.decode([tampered]))


def test_codec_reads_old_keys_after_rotation_and_refuses_unsealed_payloads() -> None:
    old = EncryptionCodec(KEY, "k1")
    sealed = asyncio.run(old.encode([Payload(data=b"x", metadata={"encoding": b"binary/plain"})]))
    rotated = EncryptionCodec(KEY, "k2")
    assert asyncio.run(rotated.decode(sealed))[0].data == b"x"
    plain = Payload(data=b"y", metadata={"encoding": b"json/plain"})
    # An unsealed payload is how a stranger on the Temporal network would start an activity.
    with pytest.raises(ValueError, match="not sealed"):
        asyncio.run(rotated.decode([plain]))
    draining = EncryptionCodec(KEY, "k2", allow_plaintext=True)  # history from before sealing
    assert asyncio.run(draining.decode([plain]))[0] == plain


def test_codec_uses_a_subkey_distinct_from_field_encryption() -> None:
    from apps.common.encryption import HKDF_INFO, derive_key
    from apps.flows.codec import HKDF_PURPOSE

    clear_key_cache()
    assert derive_key("test-v1", HKDF_PURPOSE) != derive_key("test-v1", HKDF_INFO)
    codec = EncryptionCodec()  # production path: ring from settings
    _roundtrip(codec, b"from settings")


# --- django.tasks ----------------------------------------------------------------------------


def test_tasks_run_inline_while_temporal_is_off() -> None:
    from django.tasks import task_backends

    assert type(task_backends["default"]).__name__ == "ImmediateBackend"


def test_the_task_backend_choice_follows_the_flag() -> None:
    from config.settings.base import TASKS

    # base.py is imported with TEMPORAL_ENABLED unset in the test environment.
    assert TASKS["default"]["BACKEND"].endswith("ImmediateBackend")


# --- structure ----------------------------------------------------------------------------


def test_workflow_modules_import_neither_django_nor_models() -> None:
    """Workflows run in Temporal's sandbox: Django there is slow, fragile and non-deterministic."""
    forbidden = (
        "django",
        "apps.privacy.services",
        "apps.privacy.catalog",
        "apps.privacy.activities",
    )
    offenders: list[str] = []
    for path in [*Path("src/apps").glob("*/workflows.py"), Path("tests/flow_fixtures.py")]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Import | ast.ImportFrom)
                and getattr(node, "col_offset", 0) == 0
            ):
                module = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
                if module and (module.startswith(forbidden) or module.endswith(".models")):
                    offenders.append(f"{path}:{node.lineno} imports {module}")
    assert not offenders, offenders


def test_registered_flows_have_unique_names_and_consistent_specs() -> None:
    for name, spec in FLOWS.items():
        assert spec.name == name
        assert spec.workflow is not None or spec.local is not None


def test_a_caller_cannot_start_a_flow_as_somebody_else(
    org_client: APIClient, organization: Organization, user: User
) -> None:
    """Review finding: identity came from the request body, so any member could run a flow as
    another tenant's user. It now comes from the authenticated caller, always."""
    victim = User.objects.create_user("victim@example.com", "a-long-password-1234")
    other = Organization.objects.create(name="Other", slug="other-tenant")
    Membership.objects.create(organization=other, user=victim, role=Membership.Role.OWNER)
    forged = org_client.post(
        "/api/v1/actions/flows.start/",
        {
            "flow": "test.greet",
            "input": {"title": "pwn", "organization_id": str(other.pk), "actor_id": str(victim.pk)},
        },
        format="json",
    )
    assert forged.status_code == 422 and "cannot be set" in json.dumps(forged.data)
    assert not Note.objects.filter(title="pwn").exists()

    # Server code that passes a payload with identity keys is overridden too.
    run = LocalEngine().start(
        "test.greet",
        {"title": "mine", "organization_id": str(other.pk), "actor_id": str(victim.pk)},
        organization=organization,
        actor=user,
    )
    note = Note.objects.get(title="mine")
    assert note.organization == organization and note.created_by == user
    assert json.loads(run.input_json)["organization_id"] == str(organization.pk)
