"""A request body that never finishes is cut off instead of holding a worker."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from django.test import override_settings

from apps.common.asgi import BodyLimitMiddleware


def _drive(receive: Any) -> tuple[int | None, bytes, bool]:
    sent: list[dict[str, Any]] = []
    reached = False

    async def inner(scope: Any, rcv: Any, send: Any) -> None:
        nonlocal reached
        reached = True

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    guarded = BodyLimitMiddleware(inner, max_bytes=1024)
    asyncio.run(guarded({"type": "http", "method": "POST", "headers": []}, receive, send))
    status = next((m["status"] for m in sent if m["type"] == "http.response.start"), None)
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, body, reached


@override_settings(REQUEST_BODY_TIMEOUT_SECONDS=0.2)
def test_a_body_that_stalls_gets_408_and_never_reaches_the_application() -> None:
    async def stalls() -> dict[str, Any]:
        await asyncio.sleep(5)
        return {"type": "http.request", "body": b"x", "more_body": True}

    status, body, reached = _drive(stalls)
    assert status == 408 and not reached
    assert json.loads(body)["error"]["code"] == "request_timeout"


@override_settings(REQUEST_BODY_TIMEOUT_SECONDS=0.3)
def test_a_body_dripped_slowly_hits_the_total_deadline_not_just_the_per_read_one() -> None:
    async def drips() -> dict[str, Any]:
        await asyncio.sleep(0.1)  # each read is quick, the whole body never finishes
        return {"type": "http.request", "body": b"x", "more_body": True}

    status, _, reached = _drive(drips)
    assert status == 408 and not reached


@override_settings(REQUEST_BODY_TIMEOUT_SECONDS=2)
def test_a_normal_body_is_unaffected() -> None:
    chunks = iter([b"ab", b"cd"])

    async def normal() -> dict[str, Any]:
        data = next(chunks)
        return {"type": "http.request", "body": data, "more_body": data == b"ab"}

    status, _, reached = _drive(normal)
    assert status is None and reached
