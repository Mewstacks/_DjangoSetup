"""Calling Temporal's async client from synchronous Django code.

A gRPC client is bound to the event loop that created it, and creating one per request would
open a connection per request. So each process owns a single background event loop in a daemon
thread and one client on it; synchronous callers hand coroutines to that loop and wait.
Works the same under gunicorn workers, ``runserver``, management commands and tests.
"""

from __future__ import annotations

import asyncio
import atexit
import contextvars
import threading
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from django.conf import settings
from temporalio.client import Client
from temporalio.service import TLSConfig

from apps.flows.converter import build_data_converter
from apps.flows.interceptors import PlatformInterceptor

T = TypeVar("T")


def tls_config() -> TLSConfig | bool | None:
    cert, key, ca = (
        settings.TEMPORAL_TLS_CLIENT_CERT,
        settings.TEMPORAL_TLS_CLIENT_KEY,
        settings.TEMPORAL_TLS_SERVER_CA,
    )
    if cert and key:
        return TLSConfig(
            client_cert=_read(cert),
            client_private_key=_read(key),
            server_root_ca_cert=_read(ca) if ca else None,
        )
    return True if settings.TEMPORAL_TLS or settings.TEMPORAL_API_KEY else None


def _read(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


async def connect_client(runtime: Any = None) -> Client:
    converter = build_data_converter()
    options: dict[str, Any] = {
        "namespace": settings.TEMPORAL_NAMESPACE,
        "data_converter": converter,
        "interceptors": _interceptors(converter),
        "tls": tls_config(),
    }
    if settings.TEMPORAL_API_KEY:
        options["api_key"] = settings.TEMPORAL_API_KEY
    if runtime is not None:
        options["runtime"] = runtime
    return await Client.connect(settings.TEMPORAL_ADDRESS, **options)


def _interceptors(converter: Any) -> list[Any]:
    interceptors: list[Any] = [PlatformInterceptor(converter.payload_converter)]
    if getattr(settings, "OTEL_ENABLED", False):
        from temporalio.contrib.opentelemetry import TracingInterceptor

        interceptors.append(TracingInterceptor())
    return interceptors


class TemporalRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._client: Client | None = None
        self._client_factory: Callable[[], Awaitable[Client]] = connect_client

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None or self._loop.is_closed():
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=loop.run_forever, name="temporal-client-loop", daemon=True
                )
                thread.start()
                self._loop, self._thread = loop, thread
                atexit.register(self.stop)
            return self._loop

    def run(self, work: Callable[[], Awaitable[T]], *, timeout: float | None = None) -> T:
        loop = self._ensure_loop()
        limit = timeout if timeout is not None else settings.TEMPORAL_CALL_TIMEOUT_SECONDS
        # The coroutine runs on the loop thread, whose context is not the caller's. Carry the
        # caller's context variables across, or the request id, organization and actor would
        # never reach the client interceptor that stamps them onto the workflow.
        caller = contextvars.copy_context()
        future = asyncio.run_coroutine_threadsafe(self._guarded(work, caller), loop)
        return future.result(limit)

    async def _guarded(self, work: Callable[[], Awaitable[T]], caller: contextvars.Context) -> T:
        for var, value in caller.items():
            var.set(value)
        return await work()

    async def client(self) -> Client:
        if self._client is None:
            self._client = await self._client_factory()
        return self._client

    def use_client_factory(self, factory: Callable[[], Awaitable[Client]]) -> None:
        """Tests point the runner at a Temporal test environment instead of a live server."""
        self._client = None
        self._client_factory = factory

    def stop(self) -> None:
        with self._lock:
            loop, self._loop, self._client = self._loop, None, None
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(loop.stop)


runner = TemporalRunner()
