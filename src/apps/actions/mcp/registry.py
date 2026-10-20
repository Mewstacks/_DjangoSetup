"""MCP resources and prompts, declared without importing FastMCP.

Tools come from the action registry. Resources (readable context: ``notes://{id}``) and prompts
(reusable instructions) are the other two MCP primitives; they are declared the same way so
their bodies are plain functions testable with the ordinary database fixtures.

Put them in ``<app>/agent.py`` - it is discovered automatically, like ``actions.py``.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from dataclasses import dataclass

from django.apps import apps

TEMPLATE_PARAM = re.compile(r"{(\w+)}")


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    uri: str
    name: str
    description: str
    scope: str
    fn: Callable[..., str]
    mime_type: str = "text/plain"

    @property
    def params(self) -> list[str]:
        return TEMPLATE_PARAM.findall(self.uri)


@dataclass(frozen=True, slots=True)
class PromptSpec:
    name: str
    description: str
    scope: str
    fn: Callable[..., str]
    params: tuple[str, ...]


RESOURCES: dict[str, ResourceSpec] = {}
PROMPTS: dict[str, PromptSpec] = {}


def mcp_resource(
    uri: str, *, scope: str, description: str, mime_type: str = "text/plain"
) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """Register ``fn(ctx, **uri_params) -> str`` as a readable resource."""

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        if uri in RESOURCES:
            raise ValueError(f"Resource {uri} is declared twice.")
        RESOURCES[uri] = ResourceSpec(
            uri=uri,
            name=fn.__name__,
            description=description,
            scope=scope,
            fn=fn,
            mime_type=mime_type,
        )
        return fn

    return decorator


def mcp_prompt(
    name: str, *, scope: str, description: str, params: tuple[str, ...] = ()
) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """Register ``fn(ctx, **params) -> str`` as a prompt template."""

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        if name in PROMPTS:
            raise ValueError(f"Prompt {name} is declared twice.")
        PROMPTS[name] = PromptSpec(
            name=name, description=description, scope=scope, fn=fn, params=params
        )
        return fn

    return decorator


def autodiscover() -> None:
    for config in apps.get_app_configs():
        module = f"{config.name}.agent"
        try:
            importlib.import_module(module)
        except ModuleNotFoundError as exc:
            if exc.name != module:
                raise


__all__ = ["PROMPTS", "RESOURCES", "PromptSpec", "ResourceSpec", "mcp_prompt", "mcp_resource"]
