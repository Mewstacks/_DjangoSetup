"""OAuth 2.1 for MCP clients: discovery, registration, and token verification on /mcp."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_application_model

from apps.accounts.models import User
from apps.actions.mcp.asgi import McpDispatcher, build_mcp_application
from apps.organizations.models import Membership, Organization
from test_mcp import Harness, fake_django, run

pytestmark = pytest.mark.django_db(transaction=True)
RESOURCE = "https://testserver/mcp"


@pytest.fixture
def mcp_app() -> McpDispatcher:
    return build_mcp_application(fake_django)


@pytest.fixture
def application(user: User) -> object:
    return get_application_model().objects.create(
        name="Test client",
        client_type="public",
        authorization_grant_type="authorization-code",
        redirect_uris="http://127.0.0.1:9999/callback",
    )


def issue(
    user: User,
    application: object,
    *,
    resource: str = RESOURCE,
    scope: str = "notes:read notes:write",
    expires_in: timedelta = timedelta(hours=1),
    token: str = "tok-valid",
) -> str:
    get_access_token_model().objects.create(
        user=user,
        token=token,
        application=application,
        expires=timezone.now() + expires_in,
        scope=scope,
        resource=[resource],
    )
    return token


def test_authorization_server_metadata_is_published_at_the_origin_root() -> None:
    reply = Client().get("/.well-known/oauth-authorization-server")
    assert reply.status_code == 200
    body = reply.json()
    assert body["authorization_endpoint"].endswith("/o/authorize/")
    assert body["token_endpoint"].endswith("/o/token/")
    assert "S256" in body["code_challenge_methods_supported"]
    assert body["registration_endpoint"].endswith("/o/register/")
    assert "notes:read" in body["scopes_supported"]


def test_anonymous_client_registration_is_off_until_an_operator_allows_it() -> None:
    payload = {
        "client_name": "Claude",
        "redirect_uris": ["http://127.0.0.1:7777/cb"],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
    }
    post = lambda: Client().post(  # noqa: E731
        "/o/register/", data=json.dumps(payload), content_type="application/json"
    )
    assert post().status_code in (401, 403)
    cache.clear()
    with override_settings(OAUTH_DCR_ANONYMOUS=True):
        assert post().status_code == 201
        statuses = [post().status_code for _ in range(25)]
    assert 201 not in statuses[-3:] and statuses[-1] in (401, 403, 429)


def test_pkce_is_mandatory_at_the_authorize_endpoint(user: User, application: object) -> None:
    client = Client()
    client.force_login(user)
    reply = client.get(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": application.client_id,  # type: ignore[attr-defined]
            "redirect_uri": "http://127.0.0.1:9999/callback",
        },
    )
    assert reply.status_code in (302, 400)
    assert "error" in (reply.headers.get("Location", "") + reply.content.decode()).lower()


def test_an_oauth_token_works_on_mcp_when_bound_to_this_resource(
    mcp_app: McpDispatcher, user: User, application: object, membership: Membership
) -> None:
    token = issue(user, application)

    async def scenario() -> None:
        async with Harness(mcp_app, token) as harness:
            listed = await harness.rpc("tools/list")
            assert listed.status == 200
            names = {t["name"] for t in listed.json()["result"]["tools"]}
            assert "notes_create" in names and "actions_undo" not in names  # scopes decide
            created = await harness.call("notes_create", {"title": "via oauth"})
            assert created["isError"] is False

    run(scenario)


def test_a_token_for_another_resource_expired_or_unknown_is_refused(
    mcp_app: McpDispatcher, user: User, application: object, membership: Membership
) -> None:
    other = issue(user, application, resource="https://other.example/mcp", token="tok-other")
    old = issue(user, application, expires_in=timedelta(seconds=-5), token="tok-old")

    async def scenario() -> None:
        async with Harness(mcp_app) as harness:
            for bad in (other, old, "unknown-token"):
                assert (await harness.rpc("tools/list", token=bad)).status == 401, bad

    run(scenario)


def test_organization_is_taken_from_the_path_or_the_single_membership(
    mcp_app: McpDispatcher,
    user: User,
    application: object,
    organization: Organization,
    membership: Membership,
) -> None:
    second = Organization.objects.create(name="Second", slug="second-org")
    Membership.objects.create(organization=second, user=user, role=Membership.Role.MEMBER)
    ambiguous = issue(user, application, token="tok-any")
    scoped = issue(user, application, resource=f"{RESOURCE}/second-org", token="tok-second")

    async def scenario() -> None:
        async with Harness(mcp_app) as harness:
            # Two memberships and no organization in the path: refuse rather than guess.
            assert (await harness.rpc("tools/list", token=ambiguous)).status == 401
            ok = await harness.rpc("tools/list", token=scoped, path="/mcp/second-org")
            assert ok.status == 200
            created = await harness.call(
                "notes_create", {"title": "x"}, token=scoped, path="/mcp/second-org"
            )
            assert created["isError"] is False
            # A token bound to one organization's resource is useless on another's path.
            wrong = await harness.rpc("tools/list", token=scoped, path=f"/mcp/{organization.slug}")
            assert wrong.status == 401

    run(scenario)

    from apps.examples.models import Note

    assert Note.objects.filter(organization=second).count() == 1
    assert Note.objects.filter(organization=organization).count() == 0


def test_a_token_without_an_audience_is_refused(
    mcp_app: McpDispatcher, user: User, application: object, membership: Membership
) -> None:
    get_access_token_model().objects.create(
        user=user,
        token="tok-noaud",
        application=application,
        expires=timezone.now() + timedelta(hours=1),
        scope="notes:read",
    )

    async def scenario() -> None:
        async with Harness(mcp_app) as harness:
            assert (await harness.rpc("tools/list", token="tok-noaud")).status == 401

    run(scenario)


def test_removed_members_lose_oauth_access(
    mcp_app: McpDispatcher, user: User, application: object, membership: Membership
) -> None:
    token = issue(user, application)
    Membership.objects.filter(pk=membership.pk).update(is_active=False)

    async def scenario() -> None:
        async with Harness(mcp_app, token) as harness:
            assert (await harness.rpc("tools/list")).status == 401

    run(scenario)


def test_a_401_tells_the_client_where_to_discover_oauth(mcp_app: McpDispatcher) -> None:
    async def scenario() -> None:
        async with Harness(mcp_app, "nope") as harness:
            reply = await harness.rpc("tools/list")
            assert reply.status == 401
            challenge = reply.headers["www-authenticate"]
            assert (
                'resource_metadata="https://testserver/.well-known/oauth-protected-resource'
                in challenge
            )
            metadata = await harness.request(
                "GET", "/.well-known/oauth-protected-resource/mcp/second-org"
            )
            body = metadata.json()
            assert body["resource"] == "https://testserver/mcp/second-org"
            assert body["authorization_servers"] == ["https://testserver/o"]
            assert "notes:read" in body["scopes_supported"]

    run(scenario)
