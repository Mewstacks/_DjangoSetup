"""One token verifier for every credential the MCP endpoint accepts.

An API key is recognised by its shape (``<prefix>_<id>_<secret>``) and resolved with the same
``authenticate_key`` REST uses. Anything else is tried as an OAuth access token, when OAuth is
enabled. The verifier decides *who* and *which scopes*; the organization is resolved here too,
because a token alone does not always name one.
"""

from __future__ import annotations

import hashlib
import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from fastmcp.server.auth import AccessToken, TokenVerifier

from apps.actions.mcp.preflight import org_slug_var, real_ip_var
from apps.apikeys.authentication import authenticate_key, parse_key
from apps.organizations.models import Membership

logger = logging.getLogger(__name__)

# AccessToken.token is required by the SDK; the real secret must never be kept on the object
# (it can end up in exception reports and debug output).
REDACTED_TOKEN = "[redacted]"  # noqa: S105


def resource_url(slug: str | None) -> str:
    base = (settings.MCP_PUBLIC_URL or "").rstrip("/")
    return f"{base}{settings.MCP_PATH}" + (f"/{slug}" if slug else "")


def _verify_key(raw: str, slug: str | None) -> AccessToken | None:
    found = authenticate_key(raw, ip=real_ip_var.get())
    if found is None:
        return None
    key = found.key
    if slug and key.organization.slug != slug:
        return None  # a key never reaches an organization other than its own
    return AccessToken(
        token=REDACTED_TOKEN,
        client_id=f"key:{key.pk}",
        scopes=list(key.scopes),
        expires_at=int(key.expires_at.timestamp()) if key.expires_at else None,
        claims={
            "kind": "key",
            "credential_id": str(key.pk),
            "user_id": str(key.user_id),
            "organization_id": str(key.organization_id),
        },
    )


def _verify_oauth(raw: str, slug: str | None) -> AccessToken | None:
    from oauth2_provider.models import get_access_token_model

    # Tokens are stored as a checksum only (COMPLIANT_BCP_RFC9700_TOKEN_STORAGE), so look the
    # presented value up by the same SHA-256 DOT computes when it issues one.
    checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    token = (
        get_access_token_model()
        .objects.select_related("user", "application")
        .filter(token_checksum=checksum)
        .first()
    )
    if token is None or not token.is_valid():
        return None
    # RFC 8707: the token must have been issued for *this* resource, or any MCP server
    # that ever saw it could replay it here.
    # A token with no audience at all is refused too: it would be valid for every server.
    bound = {str(entry).rstrip("/") for entry in (token.resource or [])}
    if resource_url(slug).rstrip("/") not in bound:
        return None
    memberships = Membership.objects.filter(
        user=token.user, is_active=True, organization__is_active=True
    ).select_related("organization")
    if slug:
        membership = memberships.filter(organization__slug=slug).first()
    else:
        options = list(memberships[:2])
        membership = options[0] if len(options) == 1 else None
    if membership is None or not token.user.is_active:
        return None
    return AccessToken(
        token=REDACTED_TOKEN,
        client_id=f"oauth:{token.pk}",
        scopes=token.scope.split(),
        expires_at=int(token.expires.timestamp()),
        resource=resource_url(slug),
        claims={
            "kind": "oauth",
            "credential_id": f"oauth:{token.pk}",
            "user_id": str(token.user_id),
            "organization_id": str(membership.organization_id),
        },
    )


def _verify_sync(raw: str) -> AccessToken | None:
    from django.db import close_old_connections

    close_old_connections()
    try:
        slug = org_slug_var.get()
        if parse_key(raw) is not None:
            return _verify_key(raw, slug)
        if settings.OAUTH_ENABLED:
            return _verify_oauth(raw, slug)
        return None
    finally:
        close_old_connections()


class PlatformTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        # Resolved on the request's own thread so contextvars set by the dispatcher
        # (client address, organization slug) are visible.
        return await sync_to_async(_verify_sync, thread_sensitive=True)(token)


__all__ = ["PlatformTokenVerifier", "resource_url"]
