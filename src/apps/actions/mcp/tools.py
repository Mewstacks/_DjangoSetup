"""Turn registry entries into FastMCP tools, resources and prompts.

This module and ``server.py`` / ``verifier.py`` / ``asgi.py`` are the whole FastMCP surface of
the project. Everything an action does is decided in ``apps.actions.runtime``; here a call is
only translated: bearer identity in, ``invoke()`` out, domain errors mapped to ``ToolError``.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import uuid
from typing import Any

from asgiref.sync import ThreadSensitiveContext, sync_to_async
from django.conf import settings
from django.db import close_old_connections
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import require_scopes
from fastmcp.server.dependencies import get_access_token
from fastmcp.tools import Tool, ToolResult
from mcp.types import ToolAnnotations

from apps.accounts.models import User
from apps.actions.context import build_context
from apps.actions.mcp.registry import PROMPTS, RESOURCES
from apps.actions.registry import REGISTRY, ActionSpec
from apps.actions.runtime import invoke
from apps.common.exceptions import DomainError
from apps.organizations.models import Organization

MAX_CONCURRENT_CALLS = 4
_semaphores: dict[int, asyncio.Semaphore] = {}


def _semaphore() -> asyncio.Semaphore:
    """A small gate per event loop, so a burst of tool calls cannot exhaust the DB pool."""
    loop_id = id(asyncio.get_running_loop())
    if loop_id not in _semaphores:
        _semaphores[loop_id] = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
    return _semaphores[loop_id]


def tool_name(action_name: str) -> str:
    prefix = settings.MCP_TOOL_PREFIX
    return (f"{prefix}_" if prefix else "") + action_name.replace(".", "_")


def _context_for(claims: dict[str, Any], scopes: list[str]) -> Any:
    user = User.objects.get(pk=claims["user_id"])
    organization = Organization.objects.get(pk=claims["organization_id"])
    return build_context(
        user=user,
        organization=organization,
        channel="mcp",
        scopes=frozenset(scopes),
        credential_id=claims["credential_id"],
    )


def _call_sync(
    name: str, claims: dict[str, Any], scopes: list[str], arguments: dict[str, Any]
) -> dict[str, Any]:
    from apps.common.context import request_id_var

    close_old_connections()
    try:
        ctx = _context_for(claims, scopes)
        ctx.request_id = request_id_var.get()
        output, _ = invoke(name, ctx, arguments)
        return output
    except DomainError as error:
        detail = error.payload()
        text = detail if isinstance(detail, str) else json.dumps(detail, default=str)
        raise ToolError(f"{error.code}: {text}") from error
    finally:
        close_old_connections()


class ActionTool(Tool):
    """A registry action exposed as an MCP tool. ``run`` is the whole adapter."""

    action_name: str

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        access = get_access_token()
        if access is None:
            raise ToolError("authentication_required: send a credential.")
        async with _semaphore(), ThreadSensitiveContext():  # type: ignore[no-untyped-call]
            output = await sync_to_async(_call_sync, thread_sensitive=True)(
                self.action_name, access.claims, list(access.scopes), arguments
            )
        spec = REGISTRY[self.action_name]
        if spec.output_model is None:
            return ToolResult(content="done")
        return ToolResult(content=json.dumps(output, default=str), structured_content=output)


def build_tool(spec: ActionSpec) -> ActionTool:
    parameters = (
        spec.input_model.model_json_schema()
        if spec.input_model
        else {"type": "object", "properties": {}}
    )
    return ActionTool(
        name=tool_name(spec.name),
        description=spec.description,
        parameters=parameters,
        output_schema=spec.output_model.model_json_schema() if spec.output_model else None,
        annotations=ToolAnnotations(title=spec.title, **spec.annotations),
        auth=require_scopes(spec.scope),
        action_name=spec.name,
    )


# --- resources and prompts ----------------------------------------------------------------


def _wrapper(fn: Any, params: list[str], kind: str, key: str) -> Any:
    """An async function with the exact parameters FastMCP should expose (all strings)."""

    async def wrapper(**kwargs: str) -> str:
        access = get_access_token()
        if access is None:
            raise ToolError("authentication_required: send a credential.")

        def run() -> str:
            close_old_connections()
            try:
                return str(fn(_context_for(access.claims, list(access.scopes)), **kwargs))
            except DomainError as error:
                raise ToolError(f"{error.code}: {error.detail}") from error
            finally:
                close_old_connections()

        async with _semaphore(), ThreadSensitiveContext():  # type: ignore[no-untyped-call]
            return await sync_to_async(run, thread_sensitive=True)()

    wrapper.__name__ = f"{kind}_{uuid.uuid5(uuid.NAMESPACE_URL, key).hex[:8]}"
    wrapper.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [inspect.Parameter(p, inspect.Parameter.KEYWORD_ONLY, annotation=str) for p in params],
        return_annotation=str,
    )
    wrapper.__annotations__ = {**dict.fromkeys(params, str), "return": str}
    return wrapper


def register_extras(server: Any) -> None:
    for resource in RESOURCES.values():
        server.resource(
            resource.uri,
            name=resource.name,
            description=resource.description,
            mime_type=resource.mime_type,
            auth=require_scopes(resource.scope),
        )(_wrapper(resource.fn, resource.params, "resource", resource.uri))
    for prompt in PROMPTS.values():
        server.prompt(
            name=prompt.name,
            description=prompt.description,
            auth=require_scopes(prompt.scope),
        )(_wrapper(prompt.fn, list(prompt.params), "prompt", prompt.name))
