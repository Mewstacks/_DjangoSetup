"""OAuth 2.1 authorization server routes.

Only what an MCP client needs: authorize, token, revoke, introspect and dynamic registration
under ``/o/``, plus the RFC 8414 metadata at the origin root (``root_urlpatterns``). The
application-management UI and OIDC endpoints that django-oauth-toolkit also ships are
deliberately not mounted.
"""

from __future__ import annotations

from django.conf import settings
from django.urls import path
from django.views.decorators.csp import csp_override
from oauth2_provider import urls as dot
from oauth2_provider import views

app_name = "oauth2_provider"

# Chrome applies ``form-action`` to the redirect that follows a form post, so a policy of
# 'self' would block the consent form from returning to the client's redirect_uri. The consent
# page has exactly one form (CSRF-protected, redirect URIs are validated against the registered
# client by DOT), so it alone runs without that directive; every other page keeps it.
CONSENT_CSP = {k: v for k, v in settings.SECURE_CSP.items() if k != "form-action"}

urlpatterns = [
    path(
        "authorize/",
        csp_override(CONSENT_CSP)(views.AuthorizationView.as_view()),  # type: ignore[arg-type]
        name="authorize",
    ),
    *dot.base_urlpatterns[1:4],  # token, revoke_token, introspect
    *dot.dcr_urlpatterns,
]
root_urlpatterns = dot.metadata_urlpatterns
