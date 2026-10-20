"""OpenAPI for actions, generated from the same pydantic models the runtime validates with.

drf-spectacular documents the two real views; the per-action paths are added here as a
post-processing hook, because ``/actions/{name}/`` is one URL pattern but N operations.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from apps.actions.registry import REGISTRY, ActionSpec

REF_TEMPLATE = "#/components/schemas/{model}"
ERROR_REF = "#/components/schemas/ErrorEnvelope"

_ERROR_SCHEMA = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["status", "code", "detail"],
            "properties": {
                "status": {"type": "integer"},
                "code": {"type": "string"},
                "detail": {},
                "request_id": {"type": ["string", "null"]},
            },
        }
    },
}


def _operation(spec: ActionSpec, refs: dict[Any, dict[str, str]]) -> dict[str, Any]:
    parameters: list[dict[str, Any]] = [
        {
            "name": "X-Organization-ID",
            "in": "header",
            "required": False,
            "schema": {"type": "string", "format": "uuid"},
            "description": "Required for session callers; fixed by an API key.",
        }
    ]
    if spec.write:
        parameters.append(
            {
                "name": "Idempotency-Key",
                "in": "header",
                "required": False,
                "schema": {"type": "string", "maxLength": 128},
                "description": "Repeat a call safely: the stored response is replayed.",
            }
        )
    errors = {
        str(code): {
            "description": text,
            "content": {"application/json": {"schema": {"$ref": ERROR_REF}}},
        }
        for code, text in {
            "401": "Authentication required",
            "403": "Missing scope or role",
            "404": "Unknown action or record",
            "409": "Idempotency conflict",
            "422": "Invalid input",
            "429": "Rate limited",
        }.items()
    }
    ok: dict[str, Any] = {"description": "Result"}
    if spec.output_model is not None:
        ok["content"] = {"application/json": {"schema": refs[(spec.output_model, "validation")]}}
    operation: dict[str, Any] = {
        "operationId": f"action_{spec.name.replace('.', '_')}",
        "summary": spec.title,
        "description": spec.description,
        "tags": [spec.domain],
        "parameters": parameters,
        "security": [{"ApiKeyAuth": []}, {"cookieAuth": []}],
        "x-required-scope": spec.scope,
        "responses": {"200": ok, **errors},
    }
    if spec.input_model is not None:
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": refs[(spec.input_model, "validation")]}},
        }
    return operation


def add_action_paths(
    result: dict[str, Any], generator: Any, request: Any, public: bool
) -> dict[str, Any]:
    specs = [s for s in REGISTRY.values() if "api" in s.channels]
    models: list[type[BaseModel]] = []
    for spec in specs:
        models.extend(m for m in (spec.input_model, spec.output_model) if m is not None)
    components = result.setdefault("components", {}).setdefault("schemas", {})
    components["ErrorEnvelope"] = _ERROR_SCHEMA
    refs: dict[Any, dict[str, str]] = {}
    if models:
        refs, schema = models_json_schema(
            [(m, "validation") for m in dict.fromkeys(models)], ref_template=REF_TEMPLATE
        )
        components.update(schema.get("$defs", {}))
    paths = result.setdefault("paths", {})
    paths.pop("/api/v1/actions/{name}/", None)
    for spec in specs:
        item: dict[str, Any] = {"post": _operation(spec, refs)}
        if not spec.write:
            get_operation = _operation(spec, refs)
            get_operation["operationId"] += "_get"
            get_operation.pop("requestBody", None)
            get_operation["description"] += "\n\nInput is passed as query parameters."
            item["get"] = get_operation
        paths[f"/api/v1/actions/{spec.name}/"] = item
    return result
