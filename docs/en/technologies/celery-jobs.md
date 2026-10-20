# Celery and background jobs

[Versão em português](../../pt-BR/tecnologias/celery-jobs.md) ·
[Back to the learning path](../learning-path.md)

## What is Celery?

Celery executes Python functions outside the web process. The API publishes a message to the Redis
**broker**; a **worker** takes and executes the task.

```text
API → Redis/broker → Celery worker → PostgreSQL/object storage
```

## Why use it?

Requests should return quickly. Email, reports, webhooks, imports, and LGPD exports can take
seconds or minutes:

```text
POST /exports → create job → return 202
worker → create file → update status
```

## Idempotency

With `ACKS_LATE`, a task is acknowledged after execution. It may run again after a worker crash.
**Idempotent** means repetition produces the same safe state.

Use idempotency keys, persist state, enforce uniqueness where possible, check state before
charging/sending/creating, and limit retries with backoff. Distributed systems do not provide a
simple “exactly once” guarantee.

## Data and privacy

Pass IDs, not bundles of personal data:

```python
@shared_task
def generate_export(request_id: str) -> None: ...
```

The worker loads the authorized record, checks state and retention, then saves results privately.

## Limits

The project sets soft/hard time limits, prefetch 1, rejection on worker loss, and worker recycling.
These reduce hangs and unfair distribution but do not replace monitoring.

Do not use Celery for tiny work that must finish before the response. It adds Redis, workers,
retries, and operational complexity.
