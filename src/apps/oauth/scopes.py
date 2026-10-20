"""OAuth scopes are the action scopes: one vocabulary for API keys, OAuth tokens and MCP."""

from __future__ import annotations

from typing import Any

from oauth2_provider.scopes import BaseScopes

from apps.actions.registry import known_scopes


def _descriptions() -> dict[str, str]:
    described: dict[str, str] = {}
    for scope in sorted(known_scopes()):
        domain, _, level = scope.partition(":")
        described[scope] = f"{level.capitalize()} {domain}"
    return described


class RegistryScopes(BaseScopes):  # type: ignore[misc]
    """Read the scope list from the action registry at request time, not at settings import."""

    def get_all_scopes(self) -> dict[str, str]:
        return _descriptions()

    def get_available_scopes(
        self, application: Any = None, request: Any = None, *args: Any, **kwargs: Any
    ) -> list[str]:
        return list(_descriptions())

    def get_default_scopes(
        self, application: Any = None, request: Any = None, *args: Any, **kwargs: Any
    ) -> list[str]:
        # Nothing by default: a client must ask for what it wants and the user sees it.
        return []


__all__ = ["RegistryScopes"]
