from __future__ import annotations

import re
import uuid
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound

from apps.common.context import request_id_var
from apps.common.network import client_ip, parse_trusted_networks

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # The id is always minted here: a caller-chosen value could collide with a real
        # request and mislead an investigation. What the caller sent is kept apart, and only
        # when it is well formed, so it can still be correlated with the client's own logs.
        supplied = request.headers.get("X-Request-ID", "")
        request.client_request_id = (  # type: ignore[attr-defined]
            supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else ""
        )
        request_id = str(uuid.uuid4())
        request.request_id = request_id  # type: ignore[attr-defined]
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)


class AdminIPAllowlistMiddleware:
    """Answer 404 on /admin/ unless the validated client IP is on ``ADMIN_ALLOWED_IPS``.

    A 404 (not 403) keeps the admin's existence unconfirmed to scanners. The list is empty in
    development, which disables the check; production settings refuse an enabled admin
    without one.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.networks = parse_trusted_networks(settings.ADMIN_ALLOWED_IPS)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # "/admin" (no slash) is redirected by CommonMiddleware, which would confirm the admin
        # exists to a scanner that is not on the list.
        if self.networks and (request.path == "/admin" or request.path.startswith("/admin/")):
            import ipaddress

            resolved = client_ip(request)
            allowed = False
            if resolved is not None:
                ip = ipaddress.ip_address(resolved)
                allowed = any(ip in network for network in self.networks)
            if not allowed:
                return HttpResponseNotFound()
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Headers Django has no setting for: Permissions-Policy and Cross-Origin-Resource-Policy.

    Permissions-Policy switches off browser features this product never uses, so an injected
    script cannot ask for the camera or location. CORP keeps other origins from embedding our
    responses (images, JSON, exports) with a no-cors request.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.permissions_policy = settings.PERMISSIONS_POLICY
        self.corp = settings.SECURE_CROSS_ORIGIN_RESOURCE_POLICY

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if self.permissions_policy and "Permissions-Policy" not in response:
            response["Permissions-Policy"] = self.permissions_policy
        if self.corp and "Cross-Origin-Resource-Policy" not in response:
            response["Cross-Origin-Resource-Policy"] = self.corp
        return response


class NoStoreMiddleware:
    """Mark API responses as uncacheable and tenant-dependent.

    The organization comes from a request header, so a shared cache that ignored ``Vary``
    could serve one tenant's body to another. ``no-store`` is the default for ``/api/``;
    a view that really is public can set its own Cache-Control first.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            if "Cache-Control" not in response:
                response["Cache-Control"] = "no-store"
            existing = response.get("Vary", "")
            if "x-organization-id" not in existing.lower():
                response["Vary"] = f"{existing}, X-Organization-ID".lstrip(", ")
        return response
