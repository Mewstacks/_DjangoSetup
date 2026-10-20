from __future__ import annotations

from drf_spectacular.extensions import OpenApiAuthenticationExtension

from apps.apikeys.models import key_prefix


class ApiKeyScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "apps.apikeys.authentication.ApiKeyAuthentication"
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": f"{key_prefix()}_<id>_<secret>",
            "description": "Scoped API key. Create one from an authenticated session.",
        }
