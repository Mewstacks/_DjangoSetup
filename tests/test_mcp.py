"""FastMCP served in-process by the ASGI dispatcher, end to end with real credentials.

There is no pytest-asyncio on purpose. ``Harness`` is a tiny lifespan-aware ASGI driver: it
runs the ``lifespan`` scope the way uvicorn does, then lets a test issue requests.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from starlette.types import Receive, Scope, Send

from apps.accounts.models import User
from apps.actions.mcp.asgi import McpDispatcher, build_mcp_application, guard_hosts
from apps.actions.models import ActionJournal, AgentRun
from apps.apikeys.models import ApiKey
from apps.audit.models import AuditEvent
from apps.common.asgi import BodyLimitMiddleware
from apps.examples.models import Note
from apps.organizations.models import Membership, Organization

SRC = Path(__file__).resolve().parents[1] / "src"
MCP_PATH = "/mcp"
FULL = ["notes:read", "notes:write", "actions:read", "actions:write"]


async def fake_django(scope: Scope, receive: Receive, send: Send) -> None:
    """Stands in for Django: the real handler needs the whole URLconf and a database."""
    body = json.dumps({"app": "django", "path": scope["path"]}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


@dataclass
class Reply:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


class Harness:
    def __init__(self, app: Any, token: str = "") -> None:
        self.app = app
        self.token = token
        self.lifespan_sent: list[dict[str, Any]] = []
        self._inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._started = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> Harness:
        async def send(message: dict[str, Any]) -> None:
            self.lifespan_sent.append(message)
            if message["type"].startswith("lifespan.startup"):
                self._started.set()

        self._inbox.put_nowait({"type": "lifespan.startup"})
        scope = {"type": "lifespan", "asgi": {"version": "3.0"}}
        self._task = asyncio.create_task(self.app(scope, self._inbox.get, send))
        await asyncio.wait_for(self._started.wait(), timeout=20)
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        assert self._task is not None
        self._inbox.put_nowait({"type": "lifespan.shutdown"})
        await asyncio.wait_for(self._task, timeout=20)

    async def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        headers: dict[str, str] | None = None,
        host: str = "localhost",
        client: str = "127.0.0.1",
    ) -> Reply:
        payload = json.dumps(body).encode() if body is not None else b""
        sent_headers = {
            "host": host,
            "content-length": str(len(payload)),
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            **(headers or {}),
        }
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(k.lower().encode(), v.encode()) for k, v in sent_headers.items()],
            "server": ("localhost", 8000),
            "client": (client, 50000),
        }
        delivered = False

        async def receive() -> dict[str, Any]:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": payload, "more_body": False}
            await asyncio.sleep(3600)
            raise AssertionError("unreachable")

        messages: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        await asyncio.wait_for(self.app(scope, receive, send), timeout=20)
        start = messages[0]
        return Reply(
            status=int(start["status"]),
            headers={k.decode().lower(): v.decode() for k, v in start["headers"]},
            body=b"".join(m.get("body", b"") for m in messages[1:]),
        )

    async def rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        path: str = MCP_PATH,
        token: str | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Reply:
        body: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            body["params"] = params
        bearer = self.token if token is None else token
        merged = {"authorization": f"Bearer {bearer}", **(headers or {})}
        return await self.request("POST", path, body, headers=merged, **kwargs)

    async def call(self, name: str, arguments: dict[str, Any] | None = None, **kw: Any) -> Any:
        reply = await self.rpc("tools/call", {"name": name, "arguments": arguments or {}}, **kw)
        assert reply.status == 200, reply.body
        return reply.json()["result"]


def run(scenario: Callable[[], Awaitable[None]]) -> None:
    asyncio.run(scenario())


@pytest.fixture
def mcp_app() -> McpDispatcher:
    return build_mcp_application(fake_django)


@pytest.fixture
def secret(user: User, organization: Organization, membership: Membership) -> str:
    return ApiKey.issue(
        user=user, organization=organization, label="agent", scopes=FULL, kind="agent"
    )[1]


db = pytest.mark.django_db(transaction=True)


def test_lifespan_runs_fastmcp_and_stops_it(mcp_app: McpDispatcher) -> None:
    async def scenario() -> None:
        assert mcp_app.ready is False
        harness = Harness(mcp_app)
        async with harness:
            assert mcp_app.ready is True
            assert harness.lifespan_sent == [{"type": "lifespan.startup.complete"}]
        assert mcp_app.ready is False
        assert harness.lifespan_sent[-1] == {"type": "lifespan.shutdown.complete"}

    run(scenario)


@db
def test_tools_are_listed_with_annotations_and_hidden_without_the_scope(
    mcp_app: McpDispatcher, secret: str, user: User, organization: Organization
) -> None:
    read_only = ApiKey.issue(
        user=user, organization=organization, label="r", scopes=["notes:read"]
    )[1]

    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            listed = await harness.rpc("tools/list")
            assert listed.status == 200
            tools = {t["name"]: t for t in listed.json()["result"]["tools"]}
            assert {"notes_create", "notes_list", "actions_undo", "actions_changes"} <= set(tools)
            assert tools["notes_list"]["annotations"]["readOnlyHint"] is True
            assert tools["notes_create"]["annotations"]["readOnlyHint"] is False
            assert tools["notes_archive"]["annotations"]["destructiveHint"] is True
            assert "title" in tools["notes_create"]["inputSchema"]["properties"]
            assert "ctx" not in tools["notes_create"]["inputSchema"]["properties"]
            assert tools["notes_create"]["description"].startswith("Create a note")

            narrow = await harness.rpc("tools/list", token=read_only)
            names = {t["name"] for t in narrow.json()["result"]["tools"]}
            assert "notes_list" in names and "notes_create" not in names

    run(scenario)


@db
def test_a_tool_call_runs_the_same_pipeline_as_rest(
    mcp_app: McpDispatcher, secret: str, organization: Organization
) -> None:
    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            reply = await harness.rpc(
                "tools/call", {"name": "notes_create", "arguments": {"title": "From MCP"}}
            )
            result = reply.json()["result"]
            assert result["isError"] is False, result
            assert result["structuredContent"]["title"] == "From MCP"
            request_id = reply.headers["x-request-id"]
            assert reply.headers["cache-control"] == "no-store"

            from asgiref.sync import sync_to_async

            @sync_to_async
            def facts() -> tuple[AuditEvent, int, int, AgentRun]:
                return (
                    AuditEvent.objects.get(action="action.notes.create"),
                    Note.objects.filter(organization=organization).count(),
                    ActionJournal.objects.count(),
                    AgentRun.objects.get(),
                )

            event, notes, journal, agent_run = await facts()
            # Parity: same audit shape as REST, the channel says where it came from, and the
            # id returned to the caller is the id in the audit trail.
            assert event.metadata["channel"] == "mcp" and event.request_id == request_id
            assert event.success and notes == 1 and journal == 1
            assert agent_run.tool_calls >= 1 and agent_run.credential_id

    run(scenario)


@db
def test_validation_errors_are_readable_and_never_echo_input(
    mcp_app: McpDispatcher, secret: str
) -> None:
    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            result = await harness.call("notes_create", {"title": "", "x": "joao@example.com"})
            assert result["isError"] is True
            text = json.dumps(result)
            assert "invalid" in text and "title" in text and "joao@example.com" not in text

    run(scenario)


@db
def test_undo_restores_and_refuses_over_a_later_edit(
    mcp_app: McpDispatcher, secret: str, organization: Organization
) -> None:
    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            created = (await harness.call("notes_create", {"title": "A"}))["structuredContent"]
            await harness.call("notes_update", {"id": created["id"], "title": "B"})
            changes = (await harness.call("actions_changes", {}))["structuredContent"]["items"]
            update = next(c for c in changes if c["op"] == "update")
            assert update["target_id"] == created["id"]

            undone = await harness.call("actions_undo", {"id": update["id"]})
            assert undone["isError"] is False
            got = (await harness.call("notes_get", {"id": created["id"]}))["structuredContent"]
            assert got["title"] == "A"

            again = await harness.call("actions_undo", {"id": update["id"]})
            assert again["isError"] is True and "already_undone" in json.dumps(again)

            # A later change by somebody else makes the older undo unsafe.
            create_change = next(c for c in changes if c["op"] == "create")
            await harness.call("notes_update", {"id": created["id"], "title": "C"})
            clash = await harness.call("actions_undo", {"id": create_change["id"]})
            assert clash["isError"] is True and "changed_since" in json.dumps(clash)

    run(scenario)


@db
def test_missing_forged_revoked_and_expired_credentials_are_401(
    mcp_app: McpDispatcher, secret: str, user: User, organization: Organization
) -> None:
    key = ApiKey.objects.get()
    prefix, public_id, _ = secret.split("_")
    expired = ApiKey.issue(
        user=user,
        organization=organization,
        label="old",
        scopes=FULL,
        expires_at=timezone.now() - timedelta(minutes=1),
    )[1]

    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            for token in ("", "garbage", f"{prefix}_{public_id}_{'0' * 64}", expired):
                reply = await harness.rpc("tools/list", token=token)
                assert reply.status == 401, token
            from asgiref.sync import sync_to_async

            await sync_to_async(key.revoke)()
            assert (await harness.rpc("tools/list")).status == 401

    run(scenario)


@db
def test_demoting_or_removing_the_owner_applies_mid_session(
    mcp_app: McpDispatcher, secret: str, membership: Membership
) -> None:
    async def scenario() -> None:
        from asgiref.sync import sync_to_async

        async with Harness(mcp_app, secret) as harness:
            assert (await harness.call("notes_create", {"title": "ok"}))["isError"] is False
            await sync_to_async(
                lambda: Membership.objects.filter(pk=membership.pk).update(
                    role=Membership.Role.AUDITOR
                )
            )()
            denied = await harness.call("notes_create", {"title": "no"})
            assert denied["isError"] is True and "read_only_role" in json.dumps(denied)
            await sync_to_async(
                lambda: Membership.objects.filter(pk=membership.pk).update(is_active=False)
            )()
            assert (await harness.rpc("tools/list")).status == 401

    run(scenario)


@db
def test_organization_in_the_path_must_match_the_key(
    mcp_app: McpDispatcher, secret: str, organization: Organization
) -> None:
    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            assert (await harness.rpc("tools/list", path=f"/mcp/{organization.slug}")).status == 200
            assert (await harness.rpc("tools/list", path="/mcp/someone-else")).status == 401

    run(scenario)


@db
def test_routing_host_origin_and_methods(mcp_app: McpDispatcher, secret: str) -> None:
    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            passthrough = await harness.request("GET", "/api/v1/health/live/")
            assert passthrough.json() == {"app": "django", "path": "/api/v1/health/live/"}
            assert (await harness.request("GET", "/mcp/")).json()["app"] == "django"
            bad_host = await harness.rpc("tools/list", host="evil.example.net")
            assert bad_host.status == 421
            bad_origin = await harness.rpc("tools/list", headers={"origin": "https://evil.example"})
            assert bad_origin.status == 403
            get = await harness.request(
                "GET", MCP_PATH, headers={"authorization": f"Bearer {secret}"}
            )
            assert get.status == 405

    run(scenario)


@db
def test_per_address_budget_applies_before_authentication(mcp_app: McpDispatcher) -> None:
    cache.clear()

    async def scenario() -> None:
        with override_settings(MCP_RATE_PER_MINUTE_IP=2):
            async with Harness(mcp_app, "nope") as harness:
                codes = [(await harness.rpc("tools/list")).status for _ in range(4)]
        assert codes[:2] == [401, 401] and codes[2:] == [429, 429]

    run(scenario)


@db
def test_oversized_bodies_are_refused_in_front_of_the_endpoint(
    mcp_app: McpDispatcher, secret: str
) -> None:
    guarded = BodyLimitMiddleware(mcp_app, max_bytes=64)

    async def scenario() -> None:
        async with Harness(guarded, secret) as harness:
            reply = await harness.rpc(
                "tools/call", {"name": "notes_create", "arguments": {"title": "x" * 500}}
            )
            assert reply.status == 413

    run(scenario)


@db
def test_resources_and_prompts_are_served_with_the_same_scopes(
    mcp_app: McpDispatcher, secret: str, organization: Organization
) -> None:
    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            created = (await harness.call("notes_create", {"title": "R", "body": "text"}))[
                "structuredContent"
            ]
            templates = (await harness.rpc("resources/templates/list")).json()["result"]
            assert any(
                t["uriTemplate"] == "notes://{note_id}" for t in templates["resourceTemplates"]
            )
            read = await harness.rpc("resources/read", {"uri": f"notes://{created['id']}"})
            assert "# R" in json.dumps(read.json()["result"])
            prompt = await harness.rpc(
                "prompts/get", {"name": "summarize_notes", "arguments": {"focus": "risks"}}
            )
            assert "risks" in json.dumps(prompt.json()["result"])

    run(scenario)


def test_guard_hosts_translates_django_wildcards() -> None:
    assert guard_hosts([".example.com", "api.test"]) == ["example.com", "*.example.com", "api.test"]


def test_flag_off_never_imports_fastmcp() -> None:
    code = (
        f"import os, sys; sys.path.insert(0, {str(SRC)!r}); os.environ['MCP_ENABLED']='false'; "
        "os.environ['DJANGO_SETTINGS_MODULE']='config.settings.local'; "
        "os.environ.setdefault('DJANGO_SECRET_KEY','x'*60); "
        "import django; django.setup(); import config.asgi; "
        "print('fastmcp' in sys.modules)"
    )
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False
    )
    assert out.stdout.strip().splitlines()[-1] == "False", out.stderr
