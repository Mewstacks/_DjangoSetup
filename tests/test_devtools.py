"""The development knowledge base and its MCP server: what an AI agent sees when it starts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from devtools import context_files, conventions, project
from devtools.mcp.server import build_server

ROOT = Path(__file__).resolve().parents[1]


# --- the generated agent files are fresh -----------------------------------------------------


def test_every_agent_facing_file_matches_what_the_code_renders() -> None:
    """Edit src/devtools/conventions.py and run scripts/gen_docs.py; never edit these by hand.

    A fresh interpreter: conventions.json lists what is *registered*, and other tests in this
    process register throwaway actions, events and settings of their own.
    """
    import subprocess
    import sys

    done = subprocess.run(
        [sys.executable, "scripts/gen_docs.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_claude_md_imports_agents_md_and_other_tools_get_the_same_rules() -> None:
    assert "@AGENTS.md" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    body = context_files.agents_body()
    assert body in (ROOT / ".cursor/rules/saas-base.mdc").read_text(encoding="utf-8")
    assert body in (ROOT / ".github/copilot-instructions.md").read_text(encoding="utf-8")
    assert "alwaysApply: true" in (ROOT / ".cursor/rules/saas-base.mdc").read_text(encoding="utf-8")


def test_llms_txt_follows_the_format_and_links_only_files_that_exist() -> None:
    text = context_files.llms_txt()
    assert text.startswith("# ") and "\n> " in text
    links = [part.split("](")[1].split(")")[0] for part in text.split("[")[1:] if "](" in part]
    assert links
    for link in links:
        assert (ROOT / link).exists(), link


def test_every_rule_names_something_that_enforces_it() -> None:
    for rule in conventions.RULES:
        assert rule.enforced_by.strip() and rule.why.strip() and rule.rule.strip(), rule.id
    ids = [rule.id for rule in conventions.RULES]
    assert len(ids) == len(set(ids))


def test_the_rulebook_mentions_only_files_and_commands_that_exist() -> None:
    for _, command in conventions.COMMANDS:
        script = next((tok for tok in command.split() if tok.endswith(".py")), "")
        if script and "/" in script:
            assert (ROOT / script).exists(), script
    for _, path in conventions.WHERE_TO_LOOK:
        for piece in path.replace(" (generated)", "").split(","):
            first = piece.strip().split(" ")[0]
            if first.startswith("docs/"):
                assert (ROOT / first.replace("*.md", "index.md")).parent.exists(), first


def test_conventions_json_lists_what_is_registered_right_now() -> None:
    data = json.loads(context_files.conventions_json())
    registered = data["registered"]
    assert "notes.create" in registered["actions"]
    assert "notes:read" in registered["scopes"]
    assert "note.created" in registered["webhook_events"]
    assert "examples.note" in registered["personal_models"]
    assert any(job.startswith("maintenance.") for job in registered["jobs"])


# --- project knowledge ----------------------------------------------------------------------------


def test_describe_project_lists_apps_with_the_convention_files_each_has() -> None:
    info = project.describe_project()
    assert info["actions"] >= 16 and info["models"] > 20
    assert "actions.py" in info["apps"]["examples"] and "privacy.py" in info["apps"]["examples"]
    assert info["switches"]["MCP_ENABLED"] is True  # test settings
    assert any("scaffold" in c["run"] for c in info["commands"])


def test_explain_action_gives_schemas_location_and_how_to_call_it() -> None:
    info = project.explain_action("notes.create")
    assert info["scope"] == "notes:write" and info["undoable"] is True
    assert info["defined_at"].startswith("src/apps/examples/actions.py:")
    assert (
        info["mcp_tool"] == "notes_create" and "POST /api/v1/actions/notes.create/" in info["rest"]
    )
    assert "title" in info["input_schema"]["properties"]
    missing = project.explain_action("notes.nope")
    assert "error" in missing and "notes.create" in missing["did_you_mean"]


def test_the_shipped_code_passes_its_own_conventions() -> None:
    # Freshness of generated files is checked in a clean process above.
    errors = [
        f for f in project.check_conventions(include_generated=False) if f.severity == "error"
    ]
    assert not errors, project.as_dicts(errors)


def test_check_conventions_catches_a_tenant_door_violation(
    tmp_path: Path, monkeypatch: Any
) -> None:
    app = tmp_path / "src/apps/bad"
    app.mkdir(parents=True)
    (app / "actions.py").write_text("def f(ctx):\n    return Thing.objects.all()\n")
    monkeypatch.setattr(project, "ROOT", tmp_path)
    found = project._scan_tenant_door()
    assert [f.rule for f in found] == ["tenant-door"] and found[0].where.endswith("actions.py:2")


def test_forbidden_patterns_are_found_and_comments_are_not(
    tmp_path: Path, monkeypatch: Any
) -> None:
    src = tmp_path / "src/apps/bad"
    src.mkdir(parents=True)
    (src / "code.py").write_text(
        "# eval(this) is only a comment\n"
        "x = pickle.loads(data)\n"
        "subprocess.run(cmd, shell=True)\n"
        "cursor.execute(f'select {y}')\n"
        "r = httpx.get(url)\n"
    )
    monkeypatch.setattr(project, "ROOT", tmp_path)
    found = project._scan_forbidden()
    rules = sorted(f.rule for f in found)
    assert rules.count("forbidden") == 3 and rules.count("outbound-http") == 1
    assert all("eval" not in f.message for f in found)


def test_lgpd_check_returns_the_entry_or_proposes_one() -> None:
    entry = project.lgpd_check("examples.note")
    assert entry["classified"] and entry["fields"]["title"] == "content"
    unknown = project.lgpd_check("nowhere.Thing")
    assert "error" in unknown


def test_lgpd_check_proposes_categories_and_flags_clear_text_for_an_unclassified_model(
    monkeypatch: Any,
) -> None:
    from apps.privacy import catalog

    monkeypatch.delitem(catalog.CATALOG, "examples.note")
    proposal = project.lgpd_check("examples.note")
    assert not proposal["classified"]
    assert proposal["guessed_categories"]["title"] == "CONTENT"
    assert (
        "title" in proposal["stored_in_clear_text"]
        and "body" not in proposal["stored_in_clear_text"]
    )
    assert (
        "personal(" in proposal["proposed_entry"]
        and "Category.CONTENT" in proposal["proposed_entry"]
    )


def test_docs_can_be_searched_and_read_but_only_from_the_docs_folder() -> None:
    hits = project.search_docs("idempotency key action")
    assert hits and hits[0]["path"].startswith("docs/en/")
    assert "action" in project.get_doc("docs/en/guides/add-an-action.md").lower()
    assert project.get_doc("AGENTS.md").startswith("# AGENTS.md")
    for forbidden in ("pyproject.toml", "../etc/passwd", "src/config/settings/base.py", ".env"):
        with pytest.raises(ValueError):
            project.get_doc(forbidden)
    assert project.search_docs("a") == []


# --- the MCP server -------------------------------------------------------------------------------


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture
def client_for_server(monkeypatch: pytest.MonkeyPatch) -> Any:
    from fastmcp import Client

    monkeypatch.chdir(ROOT)  # build_server changes into the project root
    return lambda: Client(build_server())


def test_the_server_offers_the_tools_resources_and_prompts_an_agent_needs(
    client_for_server: Any,
) -> None:
    async def go() -> tuple[set[str], set[str], set[str]]:
        async with client_for_server() as client:
            tools = {t.name for t in await client.list_tools()}
            resources = {str(r.uri) for r in await client.list_resources()}
            prompts = {p.name for p in await client.list_prompts()}
            return tools, resources, prompts

    tools, resources, prompts = _run(go())
    assert {
        "describe_project", "list_conventions", "list_actions", "explain_action", "lgpd_check",
        "check_conventions", "scaffold_resource", "run_gate", "search_docs", "get_doc",
    } <= tools  # fmt: skip
    assert {
        "conventions://rules",
        "catalog://actions",
        "catalog://privacy",
        "agents://guide",
    } <= resources
    assert {"add-resource", "add-action", "lgpd-review", "security-review"} <= prompts


def test_tools_return_real_answers_over_the_protocol(client_for_server: Any) -> None:
    async def go() -> dict[str, Any]:
        async with client_for_server() as client:
            described = await client.call_tool("describe_project", {})
            explained = await client.call_tool("explain_action", {"name": "notes.update"})
            checked = await client.call_tool("check_conventions", {})
            planned = await client.call_tool(
                "scaffold_resource",
                {"app": "invoices", "model": "Invoice", "fields": "title:str"},
            )
            refused = await client.call_tool(
                "scaffold_resource", {"app": "accounts", "model": "X", "fields": "title:str"}
            )
            return {
                "described": described.data,
                "explained": explained.data,
                "checked": checked.data,
                "planned": planned.data,
                "refused": refused.data,
            }

    out = _run(go())
    assert out["described"]["name"] == "saas-django-backend"
    assert out["explained"]["scope"] == "notes:write"
    problems = [f for f in out["checked"]["findings"] if f["rule"] != "generated-files"]
    assert not [f for f in problems if f["severity"] == "error"], problems
    assert out["planned"]["dry_run"] is True
    assert "src/apps/invoices/actions.py" in out["planned"]["files"]
    assert "taken" in out["refused"]["error"]
    assert not (ROOT / "src/apps/invoices").exists(), "a dry run must write nothing"


def test_the_docs_resource_and_prompts_work(client_for_server: Any) -> None:
    async def go() -> tuple[str, list[str], str]:
        refused: list[str] = []
        async with client_for_server() as client:
            page = await client.read_resource("docs://en/architecture.md")
            for escape in ("docs://../pyproject.toml", "docs://en/../../pyproject.toml"):
                try:
                    reply = await client.read_resource(escape)
                    refused.append(reply[0].text)  # the tool-level refusal text
                except Exception as error:  # the protocol-level "resource not found"
                    refused.append(f"error: {error}")
            prompt = await client.get_prompt("lgpd-review", {"model": "billing.Invoice"})
            return (
                page[0].text,
                refused,
                prompt.messages[0].content.text,  # type: ignore[union-attr]
            )

    page, refused, prompt = _run(go())
    assert "Architecture" in page
    assert all(text.startswith("error:") for text in refused), refused
    assert "billing.Invoice" in prompt and "not legal advice" in prompt
