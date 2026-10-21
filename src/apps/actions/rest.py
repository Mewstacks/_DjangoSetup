"""REST adapter: a catalog and one generic invoke endpoint over the action registry.

Resource CRUD (lists, filters, pagination, nested routes) stays in DRF viewsets, where it is
at home; actions are the RPC surface for operations. Both call the same service functions, so
there is one implementation of each rule.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.actions.context import ActionContext
from apps.actions.registry import REGISTRY, ActionSpec, get_action
from apps.actions.runtime import invoke
from apps.apikeys.authentication import ApiKeyScopePermission
from apps.apikeys.models import ApiKey
from apps.common.context import request_id_var
from apps.common.exceptions import Invalid, NotFound
from apps.common.network import client_ip
from apps.organizations.models import Membership


def context_from_request(request: Request, *, channel: str = "api") -> ActionContext:
    http = request._request
    membership = getattr(http, "organization_membership", None)
    if membership is None:
        raise Invalid(
            "Select an organization with X-Organization-ID.", code="organization_required"
        )
    assert isinstance(membership, Membership)
    key = request.auth if isinstance(request.auth, ApiKey) else None
    return ActionContext(
        user=request.user,
        organization=membership.organization,
        membership=membership,
        scopes=frozenset(key.scopes) if key else frozenset({"*"}),
        channel=channel,
        request_id=request_id_var.get(),
        credential_id=str(key.pk) if key else None,
        client_ip=client_ip(http),
    )


def describe(spec: ActionSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "title": spec.title,
        "description": spec.description,
        "scope": spec.scope,
        "write": spec.write,
        "channels": sorted(spec.channels),
        # Properties that change who may do what or how safely: dropping `roles=` or flipping
        # `destructive` must show up in the committed catalog diff, not only in code review.
        "roles": sorted(spec.roles) if spec.roles else None,
        "destructive": spec.destructive,
        "idempotent": spec.idempotent,
        "audit": spec.audit,
        "undoable": spec.undoable,
        "input_schema": spec.input_model.model_json_schema() if spec.input_model else None,
        "output_schema": spec.output_model.model_json_schema() if spec.output_model else None,
    }


class ActionCatalogView(APIView):
    """Actions the caller may use, with their input and output JSON Schemas."""

    allow_api_key = True
    permission_classes = [IsAuthenticated, ApiKeyScopePermission]

    @extend_schema(
        responses=inline_serializer(
            "ActionCatalog",
            {
                "items": serializers.ListField(child=serializers.DictField()),
                "total": serializers.IntegerField(),
            },
        )
    )
    def get(self, request: Request) -> Response:
        ctx = context_from_request(request)
        visible = [
            describe(spec)
            for spec in sorted(REGISTRY.values(), key=lambda s: s.name)
            if "api" in spec.channels and ctx.has_scope(spec.scope)
        ]
        return Response({"items": visible, "total": len(visible)})


@extend_schema(exclude=True)  # documented per action by apps.actions.schema
class ActionInvokeView(APIView):
    allow_api_key = True
    permission_classes = [IsAuthenticated, ApiKeyScopePermission]
    parser_classes = [JSONParser]

    def _invoke(self, request: Request, name: str, payload: dict[str, Any] | None) -> Response:
        ctx = context_from_request(request)
        output, replayed = invoke(
            name, ctx, payload, idempotency_key=request.headers.get("Idempotency-Key")
        )
        response = Response(output)
        if replayed:
            response["Idempotent-Replayed"] = "true"
        return response

    def get(self, request: Request, name: str) -> Response:
        spec = get_action(name)
        if spec is None or spec.write:
            raise NotFound("Unknown action.")  # a write action is not reachable by GET
        return self._invoke(request, name, request.query_params.dict())

    def post(self, request: Request, name: str) -> Response:
        data = request.data
        if not isinstance(data, dict):
            raise Invalid("The body must be a JSON object.")
        return self._invoke(request, name, dict(data))
