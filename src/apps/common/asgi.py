"""ASGI-level guards that run before Django (and before any mounted sub-application)."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from django.conf import settings

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[..., Awaitable[None]]

_TOO_LARGE = json.dumps(
    {"error": {"status": 413, "code": "payload_too_large", "detail": "Request body too large."}}
).encode()


async def _reject(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_TOO_LARGE)).encode()),
                (b"cache-control", b"no-store"),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": _TOO_LARGE})


class BodyLimitMiddleware:
    """Refuse request bodies above ``DATA_UPLOAD_MAX_MEMORY_SIZE`` with 413.

    A declared ``Content-Length`` over the limit is rejected without reading anything. A body
    without one (chunked) is read into memory up to the limit and replayed to the application;
    the first byte past the limit aborts the request. The buffer is therefore bounded by the
    limit, never by what the client chooses to send.
    """

    def __init__(self, app: ASGIApp, max_bytes: int | None = None) -> None:
        self.app = app
        self.max_bytes = max_bytes

    @property
    def limit(self) -> int:
        if self.max_bytes is not None:
            return self.max_bytes
        return int(settings.DATA_UPLOAD_MAX_MEMORY_SIZE)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return

        limit = self.limit
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = limit + 1
                if declared > limit:
                    await _reject(send)
                    return
                break

        messages: list[Message] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                # http.disconnect before the body finished: nothing to serve.
                await self.app(scope, receive, send)
                return
            total += len(message.get("body", b""))
            if total > limit:
                await _reject(send)
                return
            messages.append(message)
            if not message.get("more_body", False):
                break

        replay = iter(messages)

        async def replay_receive() -> Message:
            try:
                return next(replay)
            except StopIteration:
                return await receive()

        await self.app(scope, replay_receive, send)
