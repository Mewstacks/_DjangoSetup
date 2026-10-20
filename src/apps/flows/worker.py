"""The Temporal worker process: ``python manage.py flows_worker``."""

from __future__ import annotations

import asyncio
import signal
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any

import structlog
from django.conf import settings
from django.core.cache import cache
from temporalio.client import Client
from temporalio.runtime import PrometheusConfig, Runtime, TelemetryConfig
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions

from apps.flows.activities import run_action, run_job, run_task
from apps.flows.declare import ACTIVITIES, FLOWS
from apps.flows.interceptors import PlatformInterceptor
from apps.flows.registry import autodiscover
from apps.flows.runner import connect_client

logger = structlog.get_logger("apps.flows.worker")
HEARTBEAT_KEY = "flows:worker:heartbeat"
HEARTBEAT_EVERY = 20


def build_runtime() -> Runtime | None:
    port = settings.TEMPORAL_METRICS_PORT
    if port <= 0:
        return None
    return Runtime(
        telemetry=TelemetryConfig(
            metrics=PrometheusConfig(bind_address=f"0.0.0.0:{port}"),
            global_tags={"app": settings.TEMPORAL_TASK_QUEUE},
        )
    )


def build_worker(client: Client) -> Worker:
    autodiscover()
    workflows = [spec.workflow for spec in FLOWS.values() if spec.workflow is not None]
    threads = settings.TEMPORAL_ACTIVITY_THREADS
    return Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=workflows,
        activities=[run_action, run_job, run_task, *ACTIVITIES],
        # Sync activities on a thread pool: the ORM works as in a request thread, and the pool
        # size is also the cap on concurrent activities so connections are never oversubscribed.
        activity_executor=ThreadPoolExecutor(max_workers=threads, thread_name_prefix="activity"),
        max_concurrent_activities=threads,
        interceptors=[PlatformInterceptor(client.data_converter.payload_converter)],
        workflow_runner=SandboxedWorkflowRunner(
            restrictions=SandboxRestrictions.default.with_passthrough_modules("apps.common.context")
        ),
        graceful_shutdown_timeout=timedelta(seconds=settings.TEMPORAL_SHUTDOWN_GRACE_SECONDS),
    )


async def _heartbeat(stop: asyncio.Event) -> None:
    """A liveness stamp the readiness check reads; a stalled worker stops writing it."""
    while not stop.is_set():
        try:
            await asyncio.to_thread(cache.set, HEARTBEAT_KEY, time.time(), HEARTBEAT_EVERY * 4)
        except Exception:
            logger.warning("heartbeat_failed")
        try:
            await asyncio.wait_for(stop.wait(), HEARTBEAT_EVERY)
        except TimeoutError:
            continue


async def run_worker() -> None:
    runtime = build_runtime()
    client = await connect_client(runtime)
    worker = build_worker(client)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        logger.info("worker_stopping")
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:  # Windows event loops have no signal handlers
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(request_stop))

    logger.info(
        "worker_started",
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        flows=sorted(FLOWS),
        threads=settings.TEMPORAL_ACTIVITY_THREADS,
    )
    heartbeat = asyncio.create_task(_heartbeat(stop))
    async with worker:
        await stop.wait()
    await heartbeat
    logger.info("worker_stopped")


def main() -> Any:
    asyncio.run(run_worker())
