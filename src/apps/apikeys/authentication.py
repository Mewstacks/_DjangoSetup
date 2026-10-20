"""Authenticating an API key - shared by REST and MCP so they can never disagree."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.core.cache import cache
from django.http import HttpRequest
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

from apps.apikeys.models import ApiKey, key_prefix
from apps.common.network import client_ip
from apps.organizations.models import Membership

if TYPE_CHECKING:
    pass

LAST_USED_RESOLUTION_SECONDS = 60
# Guessing the secret behind a known public id: a few tries a minute is plenty for a person
# who mistyped a header and nothing for a script.
FAILED_PER_MINUTE = 20


@dataclass(frozen=True, slots=True)
class KeyAuth:
    key: ApiKey
    membership: Membership


def parse_key(raw: str) -> tuple[str, str] | None:
    pieces = raw.strip().split("_")
    if len(pieces) != 3 or pieces[0] != key_prefix() or not pieces[1] or not pieces[2]:
        return None
    return pieces[1], pieces[2]


def _failure_key(public_id: str) -> str:
    return f"apikey:auth-fail:{hashlib.sha256(public_id.encode()).hexdigest()[:24]}"


def _failed_too_often(public_id: str) -> bool:
    key = _failure_key(public_id)
    try:
        cache.add(key, 0, 60)
        return int(cache.get(key, 0)) >= FAILED_PER_MINUTE
    except Exception:
        return False


def _count_failure(public_id: str) -> None:
    key = _failure_key(public_id)
    try:
        cache.add(key, 0, 60)
        cache.incr(key)
    except Exception:
        return


def ip_allowed(key: ApiKey, ip: str | None) -> bool:
    if not key.allowed_ips:
        return True
    if ip is None:
        return False
    address = ipaddress.ip_address(ip)
    for entry in key.allowed_ips:
        try:
            if address in ipaddress.ip_network(str(entry), strict=False):
                return True
        except ValueError:
            continue
    return False


def authenticate_key(raw: str, *, ip: str | None = None) -> KeyAuth | None:
    """The key row and its owner's *current* membership, or ``None``.

    ``None`` carries no reason on purpose: callers answer one generic 401, so a probe learns
    nothing about whether a public id exists, was revoked or belongs to a removed member.
    """
    parsed = parse_key(raw)
    if parsed is None:
        return None
    public_id, secret = parsed
    if _failed_too_often(public_id):
        return None
    key = (
        ApiKey.objects.select_related("user", "organization")
        .filter(public_id=public_id, revoked_at__isnull=True)
        .first()
    )
    if key is None or not hmac.compare_digest(ApiKey.index_for(secret), key.secret_index):
        _count_failure(public_id)
        return None
    if not key.is_active or not key.user.is_active or not key.organization.is_active:
        return None
    if not ip_allowed(key, ip):
        return None
    membership = Membership.objects.filter(
        organization=key.organization, user=key.user, is_active=True
    ).first()
    if membership is None:
        return None
    now = timezone.now()
    if key.last_used_at is None or (now - key.last_used_at).total_seconds() >= (
        LAST_USED_RESOLUTION_SECONDS
    ):
        ApiKey.objects.filter(pk=key.pk).update(last_used_at=now, updated_at=now)
    return KeyAuth(key=key, membership=membership)


class ApiKeyAuthentication(BaseAuthentication):
    """``Authorization: Bearer <prefix>_<id>_<secret>``.

    Returns ``None`` (not an error) for any other bearer shape so a different authenticator,
    such as OAuth, can claim it. A well-formed key that fails is a 401.
    """

    keyword = "Bearer"

    def authenticate_header(self, request: Request) -> str:
        return self.keyword

    def authenticate(self, request: Request) -> tuple[object, ApiKey] | None:
        header = request.headers.get("Authorization", "")
        parts = header.split()
        if len(parts) != 2 or parts[0].casefold() != self.keyword.casefold():
            return None
        if parse_key(parts[1]) is None:
            return None
        http_request: HttpRequest = request._request
        found = authenticate_key(parts[1], ip=client_ip(http_request))
        if found is None:
            raise AuthenticationFailed("Invalid credentials.")
        # Make the key look like a selected organization to the rest of the stack (tenant
        # viewsets, permissions) - the organization is fixed by the key, never by a header.
        http_request.organization = found.key.organization  # type: ignore[attr-defined]
        http_request.organization_membership = found.membership  # type: ignore[attr-defined]
        return found.key.user, found.key


class ApiKeyScopePermission(BasePermission):
    """A key may only reach endpoints that declare which scope they need.

    Session users are not affected. For a key, a view must set ``required_scopes`` (a mapping
    of ``read``/``write`` to a scope) or ``allow_api_key = True``; anything else is refused, so
    a new endpoint is closed to keys until somebody decides what it requires.
    """

    message = "This credential cannot use this endpoint."

    def has_permission(self, request: Request, view: Any) -> bool:
        key = request.auth
        if not isinstance(key, ApiKey):
            return True
        if getattr(view, "allow_api_key", False):
            return True
        scopes = getattr(view, "required_scopes", None)
        if not scopes:
            return False
        needed = scopes["read" if request.method in SAFE_METHODS else "write"]
        granted = set(key.scopes)
        if needed not in granted and "*" not in granted:
            return False
        if request.method not in SAFE_METHODS:
            membership = getattr(request, "organization_membership", None)
            return bool(membership and membership.role in {"owner", "admin", "member"})
        return True
