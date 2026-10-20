"""The events this platform can send. Declare yours in ``<app>/events.py``.

Events are deliberately *thin*: an id and a type, not the document. A receiver that wants the
data calls the API with its own credentials, so a leaked or misrouted webhook exposes an id,
not personal data, and the receiver always sees the current state under current permissions.
"""

from __future__ import annotations

import importlib

from django.apps import apps

EVENT_TYPES: dict[str, str] = {}


def register_event(event_type: str, description: str) -> None:
    if event_type in EVENT_TYPES:
        raise ValueError(f"Event {event_type} is declared twice.")
    EVENT_TYPES[event_type] = description


register_event("webhook.test", "Sent when you press 'test' on an endpoint.")


def autodiscover() -> None:
    for config in apps.get_app_configs():
        module = f"{config.name}.events"
        try:
            importlib.import_module(module)
        except ModuleNotFoundError as exc:
            if exc.name != module:
                raise
