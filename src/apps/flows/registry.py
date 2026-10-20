"""Flow and job registry plus startup discovery (the declarations live in ``declare``)."""

from __future__ import annotations

import importlib

from django.apps import apps

from apps.flows.declare import (
    ACTIVITIES,
    FLOWS,
    JOBS,
    FlowSpec,
    JobSpec,
    activity,
    flow,
    job,
    local_flow,
)

__all__ = [
    "ACTIVITIES",
    "FLOWS",
    "JOBS",
    "FlowSpec",
    "JobSpec",
    "activity",
    "autodiscover",
    "flow",
    "job",
    "local_flow",
]


def autodiscover() -> None:
    """Import ``workflows``, ``activities`` and ``jobs`` of every installed app."""
    for config in apps.get_app_configs():
        for suffix in ("workflows", "activities", "jobs"):
            module = f"{config.name}.{suffix}"
            try:
                importlib.import_module(module)
            except ModuleNotFoundError as exc:
                if exc.name != module:
                    raise
