"""The scaffold writes code that works, not code that merely looks right."""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from devtools import scaffold

ROOT = Path(__file__).resolve().parents[1]
FIELDS = "title:str,notes:text,quantity:int,paid:bool,amount:decimal,due:datetime"


def test_every_generated_file_parses_and_names_the_resource() -> None:
    files = scaffold.render("invoices", "Invoice", scaffold.parse_fields(FIELDS))
    assert {
        "src/apps/invoices/models.py",
        "src/apps/invoices/services.py",
        "src/apps/invoices/actions.py",
        "src/apps/invoices/undo.py",
        "src/apps/invoices/privacy.py",
        "src/apps/invoices/agent.py",
        "src/apps/invoices/events.py",
        "tests/test_invoices.py",
    } <= set(files)
    for name, source in files.items():
        ast.parse(source, filename=name)
    assert "undoable=True" in files["src/apps/invoices/actions.py"]
    assert "DECIDE" in files["src/apps/invoices/privacy.py"]
    assert "EncryptedTextField" in files["src/apps/invoices/models.py"]  # text is encrypted


@pytest.mark.parametrize(
    "app, model, fields, message",
    [
        ("Invoices", "Invoice", "title", "snake_case"),
        ("invoices", "invoice", "title", "CamelCase"),
        ("accounts", "Invoice", "title", "taken"),
        ("invoices", "Invoice", "", "at least one field"),
        ("invoices", "Invoice", "title:uuid", "not one of"),
        ("invoices", "Invoice", "id:str", "already exists"),
        ("invoices", "Invoice", "class:str", "keyword"),
        ("invoices", "Invoice", "aa:str,aa:int", "twice"),
    ],
)
def test_bad_names_and_fields_are_refused(app: str, model: str, fields: str, message: str) -> None:
    with pytest.raises(scaffold.ScaffoldError, match=message):
        scaffold.render(app, model, scaffold.parse_fields(fields))


def test_write_refuses_to_overwrite_and_registers_the_app(tmp_path: Path) -> None:
    settings = tmp_path / "src/config/settings/base.py"
    settings.parent.mkdir(parents=True)
    settings.write_text('LOCAL_APPS = [\n    "apps.common",\n    "apps.examples",\n]\n')
    files = scaffold.render("invoices", "Invoice", scaffold.parse_fields("title:str"))
    written = scaffold.write(tmp_path, files, app="invoices")
    assert "src/apps/invoices/models.py" in written
    assert '    "apps.invoices",' in settings.read_text()
    scaffold.write(tmp_path, {}, app="invoices")  # registering twice adds nothing
    assert settings.read_text().count("apps.invoices") == 1
    with pytest.raises(scaffold.ScaffoldError, match="overwrite"):
        scaffold.write(tmp_path, files, app="invoices")


@pytest.mark.slow_scaffold
def test_the_generated_resource_passes_its_own_tests_and_the_platform_gates(
    tmp_path: Path,
) -> None:
    """Copy the project, scaffold into the copy, migrate, and run the generated tests there."""
    project = tmp_path / "project"
    project.mkdir()
    shutil.copytree(
        ROOT / "src",
        project / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
    )
    (project / "tests").mkdir()
    for name in ("conftest.py", "flow_fixtures.py"):
        shutil.copy(ROOT / "tests" / name, project / "tests" / name)
    shutil.copy(ROOT / "pyproject.toml", project / "pyproject.toml")
    shutil.copy(ROOT / "manage.py", project / "manage.py")
    # The copy must not see the original project's installed `src` (an editable install).
    # ...nor the outer run's external database: the copy runs on its own SQLite file.
    env = {
        **{
            k: v
            for k, v in os.environ.items()
            if not k.startswith("DB_") and k != "TEST_USE_EXTERNAL_SERVICES"
        },
        "PYTHONPATH": str(project / "src"),
        "DJANGO_SETTINGS_MODULE": "config.settings.test",
    }

    files = scaffold.render("invoices", "Invoice", scaffold.parse_fields(FIELDS))
    scaffold.write(project, files, app="invoices")

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [sys.executable, *args],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )

    migrated = run("manage.py", "makemigrations", "invoices")
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr
    # What `manage.py scaffold` leaves behind passes the platform's own lint and formatter.
    sources = [
        *sorted(
            str(path.relative_to(project)) for path in (project / "src/apps/invoices").glob("*.py")
        ),
        "tests/test_invoices.py",
    ]
    for command in (["check"], ["format", "--check"]):
        checked = run("-m", "ruff", *command, *sources)
        assert checked.returncode == 0, checked.stdout + checked.stderr
    tested = run("-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_invoices.py")
    assert tested.returncode == 0, tested.stdout[-3000:] + tested.stderr[-2000:]
    assert "4 passed" in tested.stdout
