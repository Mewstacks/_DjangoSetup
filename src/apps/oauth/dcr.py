"""Who may register an OAuth client dynamically (RFC 7591), and what they may register."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, cast
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from oauth2_provider.dcr import IsAuthenticatedDCRPermission

from apps.common.network import client_ip_bucket

PER_HOUR = 20
MAX_REDIRECT_URIS = 5
MAX_URI_LENGTH = 2048
MAX_NAME_LENGTH = 100
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
ALLOWED_GRANTS = {"authorization_code", "refresh_token"}


class DCRPermission:
    """Signed-in users always; anonymous callers only when ``OAUTH_DCR_ANONYMOUS`` is on.

    MCP clients register themselves before any user is involved, which is why the anonymous
    mode exists. It is throttled per client address, and a registered client still gets no
    token until a user consents to it on the authorize screen, so a flood of registrations
    costs rows, not access.
    """

    def has_permission(self, request: Any) -> bool:
        if IsAuthenticatedDCRPermission().has_permission(request):
            return True
        if not settings.OAUTH_DCR_ANONYMOUS:
            return False
        key = f"oauth:dcr:{client_ip_bucket(request)}:{int(time.time() // 3600)}"
        try:
            cache.add(key, 0, 7200)
            return int(cache.incr(key)) <= PER_HOUR
        except Exception:
            return False


def problem_with(metadata: Any) -> str | None:
    """Why a registration document must be refused, or ``None``.

    DOT validates the shape; this decides policy. The two things worth refusing before a user
    ever sees a consent screen: grants a public MCP client has no use for (``client_credentials``
    would mint tokens with no user at all) and redirect URIs that are not a place a browser can
    safely send an authorization code (plain ``http`` off loopback, wildcards, fragments).
    """
    if not isinstance(metadata, dict):
        return "The registration must be a JSON object."
    grants = metadata.get("grant_types", ["authorization_code"])
    if not isinstance(grants, list) or not set(grants) <= ALLOWED_GRANTS:
        return "Only the authorization_code and refresh_token grants can be registered."
    name = metadata.get("client_name", "")
    if not isinstance(name, str) or len(name) > MAX_NAME_LENGTH:
        return "client_name is too long."
    uris = metadata.get("redirect_uris", [])
    if not isinstance(uris, list) or len(uris) > MAX_REDIRECT_URIS:
        return "Register at most five redirect URIs."
    allowed_schemes = cast(
        list[str], settings.OAUTH2_PROVIDER.get("ALLOWED_REDIRECT_URI_SCHEMES", [])
    )
    extra_schemes = {scheme.casefold() for scheme in allowed_schemes} - {"http", "https"}
    for uri in uris:
        if not isinstance(uri, str) or len(uri) > MAX_URI_LENGTH or "*" in uri:
            return "A redirect URI is malformed."
        parsed = urlparse(uri)
        if parsed.fragment or not parsed.scheme:
            return "A redirect URI may not carry a fragment and must have a scheme."
        scheme = parsed.scheme.casefold()
        if scheme == "https" and parsed.hostname:
            continue
        if scheme == "http" and parsed.hostname in LOOPBACK_HOSTS:
            continue
        if scheme in extra_schemes:
            continue
        return "Redirect URIs must be https, an http loopback address, or an allowed app scheme."
    return None


def restrict_registration(
    view: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """Apply ``problem_with`` to the body of a registration (POST) or update (PUT)."""

    @wraps(view)
    def guarded(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.method in {"POST", "PUT"}:
            try:
                metadata = json.loads(request.body or b"{}")
            except ValueError:
                metadata = None
            issue = problem_with(metadata)
            if issue:
                return JsonResponse(
                    {"error": "invalid_client_metadata", "error_description": issue}, status=400
                )
        return view(request, *args, **kwargs)

    return guarded
