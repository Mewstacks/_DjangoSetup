"""Flags and settings as actions: the app, an agent or a flow asks what is on for this caller."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from apps.actions.context import ActionContext
from apps.actions.registry import action
from apps.flags import services
from apps.flags.registry import SETTINGS


class FlagState(BaseModel):
    flags: dict[str, bool]


class SettingValue(BaseModel):
    key: str = Field(min_length=1, max_length=120)


class SettingOut(BaseModel):
    key: str
    value: Any
    description: str


@action("flags.evaluate", scope="flags:read")
def evaluate(ctx: ActionContext) -> FlagState:
    """Which feature flags are on for you in this organization."""
    return FlagState(flags=services.evaluate_all(organization=ctx.organization, user=ctx.user))


@action("settings.get", scope="flags:read")
def get_setting(ctx: ActionContext, data: SettingValue) -> SettingOut:
    """The effective value of a runtime setting for this organization."""
    spec = SETTINGS.get(data.key)
    if spec is None:
        from apps.common.exceptions import NotFound

        raise NotFound("Unknown setting.")
    return SettingOut(
        key=data.key,
        value=services.get_setting(data.key, organization=ctx.organization),
        description=spec.description,
    )
