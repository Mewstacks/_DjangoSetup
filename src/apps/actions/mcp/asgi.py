"""ASGI dispatcher that serves FastMCP at ``/mcp`` next to Django.

Django's ASGI handler ignores the ``lifespan`` scope and runs each request through its own
middleware and connection handling. FastMCP needs its lifespan (the streamable-HTTP session
manager lives there), and a request to ``/mcp`` bypasses every Django middleware. So this
class owns the lifespan scope, answers the MCP paths itself after a shared pre-flight
(``preflight.py``) and hands everything else, unchanged, to Django.

Only ``config.asgi`` imports this module, and only when ``MCP_ENABLED`` is true.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable, Iterable
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from typing import Any

from django.conf import settings
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from apps.actions.mcp import preflight
from apps.actions.mcp.server import build_server
from apps.actions.mcp.verifier import resource_url
from apps.common.context import request_id_var
from apps.common.exceptions import error_body

logger = logging.getLogger(__name__)

DjangoApp = Callable[..., Awaitable[None]]
SLUG = r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]"


def guard_hosts(allowed_hosts: Iterable[str]) -> list[str]:
    """Translate Django ``ALLOWED_HOSTS`` into the patterns FastMCP's Host guard matches.

    Django writes ``.example.com`` for the domain and every subdomain; FastMCP matches with
    ``fnmatch``, so that becomes ``example.com`` plus ``*.example.com``.
    """
    hosts: list[str] = []
    for host in allowed_hosts:
        if host.startswith("."):
            hosts.extend([host[1:], f"*{host}"])
        else:
            hosts.append(host)
    return hosts


def guard_origins(hosts: list[str]) -> list[str]:
    origins = [f"https://{host}" for host in hosts]
    if settings.DEBUG:
        origins += [f"http://{host}" for host in hosts]
    return [*origins, *settings.MCP_ALLOWED_ORIGINS]


class McpDispatcher:
    def __init__(
        self,
        django_app: DjangoApp,
        mcp_app: ASGIApp,
        lifespan: Callable[[], AbstractAsyncContextManager[Any]],
    ) -> None:
        self._django_app = django_app
        self._mcp_app = mcp_app
        self._lifespan_context = lifespan
        # False until the FastMCP lifespan has started. A failed startup leaves Django
        # serving and /mcp answering 503 instead of taking the whole site down with it.
        self.ready = False
        base = re.escape(settings.MCP_PATH)
        self._path = re.compile(rf"^{base}(?:/(?P<slug>{SLUG}))?$")
        self._metadata = re.compile(
            rf"^/\.well-known/oauth-protected-resource{base}(?:/(?P<slug>{SLUG}))?$"
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._run_lifespan(receive, send)
        elif scope["type"] == "http":
            if match := self._path.fullmatch(scope["path"]):
                await self._serve(scope, receive, send, match.group("slug"))
            elif settings.OAUTH_ENABLED and (match := self._metadata.fullmatch(scope["path"])):
                await self._protected_resource_metadata(scope, receive, send, match.group("slug"))
            else:
                await self._django_app(scope, receive, send)
        else:
            await self._django_app(scope, receive, send)

    async def _serve(self, scope: Scope, receive: Receive, send: Send, slug: str | None) -> None:
        request_id = preflight.new_request_id()
        address = preflight.client_address(scope)
        tokens = (
            request_id_var.set(request_id),
            preflight.client_ip_var.set(address),
            preflight.org_slug_var.set(slug),
        )
        try:
            if not self.ready:
                response = JSONResponse(
                    error_body(503, "mcp_unavailable", "The MCP endpoint is starting."),
                    status_code=503,
                    headers={"Retry-After": "5", "Cache-Control": "no-store"},
                )
                await response(scope, receive, self._decorate(send, request_id, slug))
                return
            if preflight.over_budget(address):
                response = JSONResponse(
                    error_body(429, "rate_limited", "Too many requests."),
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
                await response(scope, receive, self._decorate(send, request_id, slug))
                return
            # FastMCP is mounted at one path; the organization segment is routing only.
            inner = {**scope, "path": settings.MCP_PATH, "raw_path": settings.MCP_PATH.encode()}
            await self._mcp_app(inner, receive, self._decorate(send, request_id, slug))
        finally:
            request_id_var.reset(tokens[0])
            preflight.client_ip_var.reset(tokens[1])
            preflight.org_slug_var.reset(tokens[2])

    def _decorate(self, send: Send, request_id: str, slug: str | None) -> Send:
        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                names = {name for name, _ in headers}
                headers.append((b"x-request-id", request_id.encode()))
                headers.extend(h for h in preflight.SECURITY_HEADERS if h[0] not in names)
                if message["status"] == 401 and settings.OAUTH_ENABLED:
                    headers = self._challenge(headers, slug)
                message = {**message, "headers": headers}
            await send(message)

        return wrapped

    @staticmethod
    def _challenge(
        headers: list[tuple[bytes, bytes]], slug: str | None
    ) -> list[tuple[bytes, bytes]]:
        """Point a 401 at the protected-resource metadata so a client can discover OAuth."""
        base = (settings.MCP_PUBLIC_URL or "").rstrip("/")
        suffix = f"/{slug}" if slug else ""
        metadata = f"{base}/.well-known/oauth-protected-resource{settings.MCP_PATH}{suffix}"
        value = f'Bearer resource_metadata="{metadata}"'.encode()
        kept = [(n, v) for n, v in headers if n.lower() != b"www-authenticate"]
        kept.append((b"www-authenticate", value))
        return kept

    async def _protected_resource_metadata(
        self, scope: Scope, receive: Receive, send: Send, slug: str | None
    ) -> None:
        """RFC 9728: tell a client which authorization server issues tokens for this resource."""
        from apps.actions.registry import known_scopes

        issuer = (settings.OAUTH_ISSUER_URL or settings.MCP_PUBLIC_URL or "").rstrip("/")
        body = {
            "resource": resource_url(slug),
            "authorization_servers": [f"{issuer}/o"],
            "bearer_methods_supported": ["header"],
            "scopes_supported": sorted(known_scopes()),
        }
        response = JSONResponse(body, headers={"Cache-Control": "public, max-age=300"})
        await response(scope, receive, send)

    async def _run_lifespan(self, receive: Receive, send: Send) -> None:
        await receive()  # lifespan.startup
        stack = AsyncExitStack()
        try:
            await stack.enter_async_context(self._lifespan_context())
            self.ready = True
        except Exception:
            logger.exception("MCP lifespan failed to start; /mcp will answer 503")
        await send({"type": "lifespan.startup.complete"})
        await receive()  # lifespan.shutdown
        self.ready = False
        try:
            await stack.aclose()
        except Exception:
            logger.exception("MCP lifespan failed to stop cleanly")
        await send({"type": "lifespan.shutdown.complete"})


def build_mcp_application(django_app: DjangoApp) -> McpDispatcher:
    hosts = guard_hosts(settings.ALLOWED_HOSTS)
    server = build_server()
    mcp_app = server.http_app(
        path=settings.MCP_PATH,
        stateless_http=True,
        json_response=True,
        host_origin_protection=True,
        allowed_hosts=hosts,
        allowed_origins=guard_origins(hosts),
    )
    return McpDispatcher(django_app, mcp_app, lambda: mcp_app.lifespan(mcp_app))


__all__ = ["McpDispatcher", "build_mcp_application", "guard_hosts"]
