"""The FastMCP server behind ``/mcp``.

Imports FastMCP at module level on purpose: ``config.asgi`` imports this package only when
``MCP_ENABLED`` is true, so with the flag off none of it is loaded.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from fastmcp import FastMCP

from apps.actions.mcp import registry
from apps.actions.mcp.tools import build_tool, register_extras
from apps.actions.mcp.verifier import PlatformTokenVerifier
from apps.actions.registry import REGISTRY


def build_server(verifier: PlatformTokenVerifier | None = None) -> FastMCP[Any]:
    registry.autodiscover()
    server: FastMCP[Any] = FastMCP(
        settings.MCP_SERVER_NAME,
        instructions=settings.MCP_INSTRUCTIONS,
        auth=verifier or PlatformTokenVerifier(),
        # Django ValidationError text and ORM errors must not reach the client; actions raise
        # DomainError for the refusals meant to be read, mapped to ToolError by the adapter.
        mask_error_details=True,
    )
    for spec in sorted(REGISTRY.values(), key=lambda s: s.name):
        if "mcp" in spec.channels:
            server.add_tool(build_tool(spec))
    register_extras(server)
    return server
