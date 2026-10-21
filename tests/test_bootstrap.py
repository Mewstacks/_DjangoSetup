"""The first-run experience: bootstrap, rename, and removing the example resource."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
from allauth.account.models import EmailAddress
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.accounts.models import User
from apps.apikeys.authentication import authenticate_key
from apps.organizations.models import Membership, Organization

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.django_db


def _bootstrap(*args: str) -> dict[str, object]:
    out = StringIO()
    call_command("bootstrap", "--json", *args, stdout=out)
    return json.loads(out.getvalue())  # type: ignore[no-any-return]


def test_bootstrap_makes_a_user_who_can_actually_sign_in_and_a_key_that_works() -> None:
    result = _bootstrap("--email", "Founder@Example.com", "--org", "My Company")
    user = User.objects.get(email="founder@example.com")
    assert user.is_superuser and user.is_staff and user.check_password(result["password"])
    assert EmailAddress.objects.get(user=user).verified  # verification is mandatory to sign in
    organization = Organization.objects.get(slug="my-company")
    assert Membership.objects.get(user=user, organization=organization).role == "owner"
    found = authenticate_key(str(result["api_key"]))
    assert found is not None and found.key.organization == organization


def test_bootstrap_is_idempotent_and_never_resets_an_existing_password() -> None:
    first = _bootstrap()
    second = _bootstrap()
    assert User.objects.count() == 1 and Organization.objects.count() == 1
    assert second["password"] == "(unchanged)" and second["created_user"] is False
    assert User.objects.get().check_password(first["password"])
    assert first["api_key"] != second["api_key"]  # a fresh key each run; the old one still works


def test_bootstrap_can_skip_the_key_and_set_a_password() -> None:
    result = _bootstrap("--no-key", "--password", "a-long-local-only-passphrase")
    assert result["api_key"] == ""
    assert User.objects.get().check_password("a-long-local-only-passphrase")


@override_settings(DEV_TOOLS_ALLOWED=False)
def test_bootstrap_refuses_outside_local_settings() -> None:
    with pytest.raises(CommandError, match="local settings"):
        call_command("bootstrap", stdout=StringIO())
    assert not User.objects.exists()


def _tree(tmp_path: Path) -> Path:
    for relative in (
        "pyproject.toml",
        "compose.yaml",
        "src/config/settings/base.py",
        "src/config/urls_api.py",
        "src/apps/common/admin.py",
        "deploy/compose/compose.prod.yaml",
        "deploy/compose/prod.env.example",
        "deploy/k8s/base/migrate-job.yaml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / relative, target)
    (tmp_path / "src/apps/examples").mkdir(parents=True)
    (tmp_path / "src/apps/examples/models.py").write_text("class Note: ...\n")
    for folder in ("tests", "scripts"):
        (tmp_path / folder).mkdir(exist_ok=True)
    (tmp_path / "tests/test_x.py").write_text("from apps.examples.models import Note\n")
    return tmp_path


def _script(name: str, *args: str) -> str:
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / name), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def test_init_project_previews_then_renames_and_is_safe_to_repeat(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    before = (root / "pyproject.toml").read_text(encoding="utf-8")
    preview = _script("init_project.py", "--name", "Acme Billing", "--root", str(root))
    assert (
        "Preview only" in preview
        and (root / "pyproject.toml").read_text(encoding="utf-8") == before
    )
    _script("init_project.py", "--name", "Acme Billing", "--root", str(root), "--apply")
    assert 'name = "acme-billing"' in (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "Acme Billing API" in (root / "src/config/settings/base.py").read_text(encoding="utf-8")
    assert "name: acme-billing" in (root / "compose.yaml").read_text(encoding="utf-8")
    again = _script("init_project.py", "--name", "Acme Billing", "--root", str(root), "--apply")
    assert "0 change(s)" in again


@pytest.mark.parametrize("bad", ['x"y', "a", "", "Bad\\Name"])
def test_init_project_refuses_names_that_would_break_the_files(bad: str, tmp_path: Path) -> None:
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts/init_project.py"), "--name", bad, "--apply"],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert done.returncode != 0


def test_remove_example_deletes_the_app_unwires_it_and_lists_what_still_uses_it(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path)
    _script("remove_example.py", "--root", str(root))
    assert (root / "src/apps/examples").exists(), "a preview deletes nothing"
    output = _script("remove_example.py", "--root", str(root), "--apply")
    assert not (root / "src/apps/examples").exists()
    assert '"apps.examples"' not in (root / "src/config/settings/base.py").read_text(
        encoding="utf-8"
    )
    assert "NoteViewSet" not in (root / "src/config/urls_api.py").read_text(encoding="utf-8")
    assert "tests/test_x.py" in output  # still mentions Note: to be ported, not silently deleted
