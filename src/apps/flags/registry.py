"""Declared settings: a key, a type and a default, so a runtime override is always valid.

# <app>/dynamic.py
declare_setting("notes.max_per_org", int, 1000, "Soft cap on notes per organization.")

get_setting("notes.max_per_org", organization=org)   # the override, else the default
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from django.apps import apps


@dataclass(frozen=True)
class SettingSpec:
    key: str
    type: type
    default: Any
    description: str


SETTINGS: dict[str, SettingSpec] = {}


def declare_setting(key: str, type_: type, default: Any, description: str) -> None:
    if key in SETTINGS:
        raise ValueError(f"Setting {key} is declared twice.")
    if not isinstance(default, type_):
        raise TypeError(f"Setting {key}: default must be a {type_.__name__}.")
    SETTINGS[key] = SettingSpec(key, type_, default, description)


def autodiscover() -> None:
    for config in apps.get_app_configs():
        module = f"{config.name}.dynamic"
        try:
            importlib.import_module(module)
        except ModuleNotFoundError as exc:
            if exc.name != module:
                raise
