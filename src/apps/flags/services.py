"""Evaluating flags and reading settings, cached and invalidated on every write."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from django.core.cache import cache

from apps.common.exceptions import Invalid
from apps.flags.models import Flag, FlagRule, Setting
from apps.flags.registry import SETTINGS

VERSION_KEY = "flags:version"
TTL = 60


def _version() -> str:
    version = cache.get(VERSION_KEY)
    if version is None:
        version = uuid.uuid4().hex
        cache.set(VERSION_KEY, version, None)
    return str(version)


def invalidate() -> None:
    cache.set(VERSION_KEY, uuid.uuid4().hex, None)


def _snapshot() -> dict[str, Any]:
    key = f"flags:snapshot:{_version()}"
    data = cache.get(key)
    if data is not None:
        return dict(data)
    flags: dict[str, Any] = {}
    for flag in Flag.objects.prefetch_related("rules"):
        flags[flag.key] = {
            "default": flag.default_enabled,
            "rules": [
                {
                    "user": str(r.user_id) if r.user_id else None,
                    "organization": str(r.organization_id) if r.organization_id else None,
                    "percentage": r.percentage,
                    "enabled": r.enabled,
                }
                for r in flag.rules.all()
            ],
        }
    settings_rows = [
        {"key": s.key, "organization": str(s.organization_id) if s.organization_id else None,
         "value": s.value}
        for s in Setting.objects.all()
    ]  # fmt: skip
    data = {"flags": flags, "settings": settings_rows}
    cache.set(key, data, TTL)
    return data


def _bucket(flag_key: str, subject_id: str) -> int:
    digest = hashlib.sha256(f"{flag_key}:{subject_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % 100


def is_enabled(key: str, *, organization: Any = None, user: Any = None) -> bool:
    flag = _snapshot()["flags"].get(key)
    if flag is None:
        return False
    org_id = str(getattr(organization, "pk", "") or "")
    user_id = str(getattr(user, "pk", "") or "")
    rules = flag["rules"]
    for rule in rules:
        if rule["user"] and rule["user"] == user_id:
            return bool(rule["enabled"])
    for rule in rules:
        if rule["organization"] and rule["organization"] == org_id:
            return bool(rule["enabled"])
    for rule in rules:
        if rule["percentage"] is not None:
            subject = user_id or org_id
            if subject and _bucket(key, subject) < rule["percentage"]:
                return bool(rule["enabled"])
    return bool(flag["default"])


def evaluate_all(*, organization: Any = None, user: Any = None) -> dict[str, bool]:
    return {
        key: is_enabled(key, organization=organization, user=user)
        for key in sorted(_snapshot()["flags"])
    }


def get_setting(key: str, *, organization: Any = None) -> Any:
    spec = SETTINGS.get(key)
    if spec is None:
        raise KeyError(f"Undeclared setting {key!r}; add declare_setting() in <app>/dynamic.py.")
    org_id = str(getattr(organization, "pk", "") or "")
    best: Any = None
    for row in _snapshot()["settings"]:
        if row["key"] != key:
            continue
        if row["organization"] == org_id and org_id:
            return row["value"]
        if row["organization"] is None:
            best = row["value"]
    return spec.default if best is None else best


def set_setting(key: str, value: Any, *, organization: Any = None) -> Setting:
    spec = SETTINGS.get(key)
    if spec is None:
        raise Invalid(f"Unknown setting {key!r}.")
    if not isinstance(value, spec.type) or isinstance(value, bool) != (spec.type is bool):
        raise Invalid(f"{key} must be a {spec.type.__name__}.")
    row, _ = Setting.objects.update_or_create(
        key=key, organization=organization, defaults={"value_json": json.dumps(value)}
    )
    invalidate()
    return row


__all__ = ["FlagRule", "evaluate_all", "get_setting", "invalidate", "is_enabled", "set_setting"]
