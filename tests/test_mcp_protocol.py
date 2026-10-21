"""Which MCP protocol revisions the server speaks, pinned so an upgrade cannot change it quietly."""

from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.actions.mcp.asgi import McpDispatcher, build_mcp_application
from apps.apikeys.models import ApiKey
from apps.organizations.models import Membership, Organization
from test_mcp import Harness, fake_django, run

pytestmark = pytest.mark.django_db(transaction=True)

# Revisions a client may ask for in `initialize`. The platform is stateless streamable HTTP, so it
# serves clients of every revision from 2025-03-26 on without a session.
SUPPORTED = ("2025-03-26", "2025-06-18", "2025-11-25")


@pytest.fixture
def mcp_app() -> McpDispatcher:
    return build_mcp_application(fake_django)


@pytest.fixture
def secret(user: User, organization: Organization, membership: Membership) -> str:
    return ApiKey.issue(
        user=user, organization=organization, label="agent", scopes=["notes:read"], kind="agent"
    )[1]


def _initialize(version: str) -> dict[str, object]:
    return {
        "protocolVersion": version,
        "capabilities": {},
        "clientInfo": {"name": "conformance", "version": "1"},
    }


@pytest.mark.parametrize("version", SUPPORTED)
def test_each_supported_revision_negotiates_itself(
    mcp_app: McpDispatcher, secret: str, version: str
) -> None:
    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            reply = await harness.rpc("initialize", _initialize(version))
            assert reply.status == 200, reply.body
            result = reply.json()["result"]
            assert result["protocolVersion"] == version
            assert result["serverInfo"]["name"]
            assert "tools" in result["capabilities"]

    run(scenario)


def test_an_unknown_revision_gets_a_revision_the_server_does_speak(
    mcp_app: McpDispatcher, secret: str
) -> None:
    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            reply = await harness.rpc("initialize", _initialize("1999-01-01"))
            assert reply.status == 200, reply.body
            offered = reply.json()["result"]["protocolVersion"]
            assert offered in SUPPORTED or offered > SUPPORTED[-1]

    run(scenario)


def test_no_session_is_needed_to_call_a_tool(mcp_app: McpDispatcher, secret: str) -> None:
    """Stateless: any replica can answer any request, which is what the 2026-07-28 revision makes
    the only mode. A client that never sends `initialize` still gets its tools."""

    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            reply = await harness.rpc("tools/list")
            assert reply.status == 200 and "mcp-session-id" not in reply.headers
            assert reply.json()["result"]["tools"]

    run(scenario)


def test_the_platform_resources_and_prompt_are_listed_for_a_read_scoped_key(
    mcp_app: McpDispatcher, user: User, organization: Organization, membership: Membership
) -> None:
    key = ApiKey.issue(
        user=user, organization=organization, label="r", scopes=["platform:read", "notes:read"]
    )[1]

    async def scenario() -> None:
        async with Harness(mcp_app, key) as harness:
            resources = (await harness.rpc("resources/list")).json()["result"]["resources"]
            assert {"platform://actions", "platform://scopes"} <= {r["uri"] for r in resources}
            prompts = (await harness.rpc("prompts/list")).json()["result"]["prompts"]
            assert "how_to_use_platform" in {p["name"] for p in prompts}
            actions = await harness.rpc("resources/read", {"uri": "platform://actions"})
            text = actions.json()["result"]["contents"][0]["text"]
            assert "notes_list" in text and "notes_create" not in text  # only what the key may do
            scopes = await harness.rpc("resources/read", {"uri": "platform://scopes"})
            assert "platform:read" in scopes.json()["result"]["contents"][0]["text"]

    run(scenario)


def test_a_key_without_platform_read_does_not_see_them(mcp_app: McpDispatcher, secret: str) -> None:
    async def scenario() -> None:
        async with Harness(mcp_app, secret) as harness:
            resources = (await harness.rpc("resources/list")).json()["result"]["resources"]
            assert "platform://actions" not in {r["uri"] for r in resources}

    run(scenario)
