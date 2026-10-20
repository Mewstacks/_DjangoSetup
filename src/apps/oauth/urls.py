"""OAuth 2.1 authorization server routes.

Only what an MCP client needs: authorize, token, revoke, introspect and dynamic registration
under ``/o/``, plus the RFC 8414 metadata at the origin root (``root_urlpatterns``). The
application-management UI and OIDC endpoints that django-oauth-toolkit also ships are
deliberately not mounted.
"""

from __future__ import annotations

from oauth2_provider import urls as dot

app_name = "oauth2_provider"

urlpatterns = [
    *dot.base_urlpatterns[:4],  # authorize, token, revoke_token, introspect
    *dot.dcr_urlpatterns,
]
root_urlpatterns = dot.metadata_urlpatterns
