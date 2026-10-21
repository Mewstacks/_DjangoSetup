"""Tenant isolation as structure: tests that fail when a new model or module forgets the rule."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from django.apps import apps
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.actions.context import build_context
from apps.actions.journal import undo_entry
from apps.actions.models import ActionJournal
from apps.apikeys.models import ApiKey
from apps.common.exceptions import NotFound
from apps.examples.models import Note
from apps.organizations import quotas
from apps.organizations.models import Membership, Organization, OrganizationScopedModel
from apps.organizations.quotas import QuotaExceeded
from devtools.project import TENANT_MODEL_EXCEPTIONS

pytestmark = pytest.mark.django_db

# Models that carry an `organization` column without being OrganizationScopedModel, and why,
# live in devtools.project so the development MCP server enforces the same list. A new tenant
# model is not added there: it subclasses OrganizationScopedModel.


def test_every_model_with_an_organization_column_is_scoped_or_explained() -> None:
    offenders = []
    for model in apps.get_models():
        field = next((f for f in model._meta.get_fields() if f.name == "organization"), None)
        if field is None or getattr(field, "related_model", None) is not Organization:
            continue
        if issubclass(model, OrganizationScopedModel):
            continue
        if model._meta.label_lower not in TENANT_MODEL_EXCEPTIONS:
            offenders.append(model._meta.label)
    assert not offenders, (
        f"{offenders}: tenant data subclasses OrganizationScopedModel; if it truly cannot, add "
        "it to TENANT_MODEL_EXCEPTIONS with the reason."
    )


def test_the_exception_list_has_no_stale_entries() -> None:
    labels = {m._meta.label_lower for m in apps.get_models()}
    assert set(TENANT_MODEL_EXCEPTIONS) <= labels


def test_modules_that_run_as_the_caller_reach_data_only_through_the_context() -> None:
    """``actions.py``, ``actions/*.py`` and MCP ``agent.py`` run on behalf of a credential."""
    paths = [
        *Path("src/apps").glob("*/actions.py"),
        *Path("src/apps").glob("*/actions/*.py"),
        *Path("src/apps").glob("*/agent.py"),
    ]
    assert paths
    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders.extend(
            f"{path}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr in {"objects", "_default_manager"}
        )
    assert not offenders, offenders


def test_undo_never_reaches_a_row_of_another_organization(
    user: User, organization: Organization, membership: Membership
) -> None:
    other = Organization.objects.create(name="Other", slug="other-org")
    foreign = Note.objects.create(organization=other, title="not yours", created_by=user)
    entry = ActionJournal.objects.create(
        organization=organization,
        user=user,
        action="notes.update",
        target_type="examples.note",
        target_id=str(foreign.pk),
        op="update",
        before={"title": "hacked"},
        after={},
    )
    ctx = build_context(user=user, organization=organization, channel="mcp", scopes=frozenset("*"))
    with pytest.raises(NotFound):
        undo_entry(ctx, entry.pk)
    foreign.refresh_from_db()
    assert foreign.title == "not yours"


def test_quotas_stop_one_organization_from_growing_without_bound(
    user: User, organization: Organization, membership: Membership, org_client: APIClient
) -> None:
    from django.test import override_settings

    with override_settings(QUOTA_API_KEYS_PER_ORG=1):
        ApiKey.issue(user=user, organization=organization, label="a", scopes=["notes:read"])
        created = org_client.post(
            "/api/v1/api-keys/", {"label": "b", "profile": "read"}, format="json"
        )
        assert created.status_code == 403 and created.json()["error"]["code"] == "quota_exceeded"
    with override_settings(QUOTA_API_KEYS_PER_ORG=0):  # 0 disables the ceiling
        quotas.api_keys(organization)


def test_upload_quota_counts_bytes_and_files(
    organization: Organization, membership: Membership, user: User
) -> None:
    from django.test import override_settings

    with override_settings(QUOTA_UPLOAD_BYTES_PER_ORG=100, QUOTA_UPLOAD_FILES_PER_ORG=10):
        quotas.uploads(organization, size=100)
        with pytest.raises(QuotaExceeded):
            quotas.uploads(organization, size=101)
    with override_settings(QUOTA_UPLOAD_FILES_PER_ORG=1, QUOTA_UPLOAD_BYTES_PER_ORG=0):
        from apps.uploads.models import UploadedFile

        UploadedFile.objects.create(
            organization=organization,
            uploaded_by=user,
            original_name="a.txt",
            content_type="text/plain",
            size=1,
            sha256="0" * 64,
        )
        with pytest.raises(QuotaExceeded):
            quotas.uploads(organization, size=1)
