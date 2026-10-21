"""Where actions are declared.

An action is a plain function ``fn(ctx, data) -> result``. Declaring it with ``@action``
records the contract - name, scope, whether it writes, which channels may call it, the
pydantic input and output models read from the type hints - and nothing else. REST, MCP,
Temporal and the CLI are *adapters* over this registry, so adding an action means writing one
function, not four integrations.

Import-time rules (they fail at startup, not in production):

* the name is ``domain.verb`` and unique;
* the docstring is non-empty - it is what a model reads as the tool description;
* a write action's scope must not be a ``:read`` scope;
* ``data`` and the return value are pydantic models.
"""

from __future__ import annotations

import importlib
import inspect
import re
import typing
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.apps import apps
from django.conf import settings
from pydantic import BaseModel

CHANNELS = frozenset({"api", "mcp", "flow", "cli"})
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")

ActionFn = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ActionSpec:
    name: str
    fn: ActionFn
    scope: str
    write: bool
    description: str
    input_model: type[BaseModel] | None
    output_model: type[BaseModel] | None
    channels: frozenset[str] = CHANNELS
    roles: frozenset[str] | None = None
    idempotent: bool = False
    destructive: bool = False
    audit: bool = False
    # True: an undo handler reverses it (apps/<app>/undo.py). A string: why it cannot be undone.
    # Only read actions leave it None.
    undoable: bool | str | None = None
    title: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def domain(self) -> str:
        return self.name.split(".", 1)[0]

    @property
    def annotations(self) -> dict[str, bool]:
        """MCP tool hints, derived so they can never disagree with ``write``."""
        return {
            "readOnlyHint": not self.write,
            "destructiveHint": self.destructive if self.write else False,
            "idempotentHint": self.idempotent or not self.write,
            "openWorldHint": False,
        }


REGISTRY: dict[str, ActionSpec] = {}


def _models_from_hints(
    fn: ActionFn, name: str
) -> tuple[type[BaseModel] | None, type[BaseModel] | None]:
    hints = typing.get_type_hints(fn)
    params = list(inspect.signature(fn).parameters)
    if not params or params[0] != "ctx":
        raise TypeError(f"Action {name}: the first parameter must be named 'ctx'.")
    if len(params) > 2:
        raise TypeError(f"Action {name}: expected fn(ctx) or fn(ctx, data).")
    input_model: type[BaseModel] | None = None
    if len(params) == 2:
        candidate = hints.get(params[1])
        if not (inspect.isclass(candidate) and issubclass(candidate, BaseModel)):
            raise TypeError(
                f"Action {name}: '{params[1]}' must be annotated with a pydantic model."
            )
        input_model = candidate
    returned = hints.get("return")
    output_model: type[BaseModel] | None = None
    if returned is not None and returned is not type(None):
        if not (inspect.isclass(returned) and issubclass(returned, BaseModel)):
            raise TypeError(f"Action {name}: the return annotation must be a pydantic model.")
        output_model = returned
    return input_model, output_model


def action(
    name: str,
    *,
    scope: str | None = None,
    write: bool = False,
    channels: frozenset[str] | set[str] = CHANNELS,
    roles: set[str] | None = None,
    idempotent: bool = False,
    destructive: bool = False,
    audit: bool | None = None,
    undoable: bool | str | None = None,
    title: str = "",
) -> Callable[[ActionFn], ActionFn]:
    """Register ``fn`` as the action ``name``. The docstring is the description models read."""

    def decorator(fn: ActionFn) -> ActionFn:
        if not NAME_PATTERN.fullmatch(name):
            raise ValueError(f"Action name {name!r} must look like 'domain.verb'.")
        if name in REGISTRY:
            raise ValueError(f"Action {name} is declared twice.")
        description = inspect.cleandoc(fn.__doc__ or "")
        if not description:
            raise ValueError(f"Action {name} needs a docstring: it is what the model reads.")
        unknown = set(channels) - CHANNELS
        if unknown:
            raise ValueError(f"Action {name}: unknown channels {sorted(unknown)}.")
        resolved_scope = scope or f"{name.split('.', 1)[0]}:{'write' if write else 'read'}"
        if write and resolved_scope.endswith(":read"):
            raise ValueError(f"Action {name}: a write action cannot use the read scope.")
        if write and undoable is None:
            raise ValueError(
                f"Action {name} writes, so say whether it can be undone: undoable=True (and "
                "register a handler in <app>/undo.py) or undoable='<why it cannot be>'. An agent "
                "that changes data must be able to take the change back, or say it cannot."
            )
        if undoable is False:
            raise ValueError(f"Action {name}: undoable=False needs the reason, as a string.")
        input_model, output_model = _models_from_hints(fn, name)
        REGISTRY[name] = ActionSpec(
            name=name,
            fn=fn,
            scope=resolved_scope,
            write=write,
            description=description,
            input_model=input_model,
            output_model=output_model,
            channels=frozenset(channels),
            roles=frozenset(roles) if roles else None,
            idempotent=idempotent,
            destructive=destructive,
            audit=write if audit is None else audit,
            undoable=undoable,
            title=title or name.replace(".", " ").replace("_", " ").title(),
        )
        return fn

    return decorator


def get_action(name: str) -> ActionSpec | None:
    return REGISTRY.get(name)


def known_scopes() -> frozenset[str]:
    extra = getattr(settings, "ACTIONS_EXTRA_SCOPES", ())
    return frozenset({spec.scope for spec in REGISTRY.values()} | set(extra))


def read_scopes() -> frozenset[str]:
    """Scopes that only ever authorise reads (a scope shared with a write action is not one)."""
    write_scopes = {spec.scope for spec in REGISTRY.values() if spec.write}
    reads = {spec.scope for spec in REGISTRY.values() if not spec.write} - write_scopes
    reads |= {s for s in getattr(settings, "ACTIONS_EXTRA_SCOPES", ()) if s.endswith(":read")}
    return frozenset(reads)


# Modules imported for every installed app. ``undo`` is here so that a handler cannot be
# forgotten by not importing it: the first undo of a change would otherwise fail at runtime.
DISCOVERED = ("actions", "undo")


def autodiscover() -> None:
    """Import ``<app>.actions`` and ``<app>.undo``, like the admin does for ``admin``."""
    for config in apps.get_app_configs():
        for suffix in DISCOVERED:
            module = f"{config.name}.{suffix}"
            try:
                importlib.import_module(module)
            except ModuleNotFoundError as exc:
                if exc.name != module:  # a real import error inside the module must surface
                    raise
