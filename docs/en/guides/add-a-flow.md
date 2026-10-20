# Add a flow or a job

- A **job** is a function run once, optionally on a cron schedule (pruning, sweeps, reminders).
- A **flow** is a durable process: waits for days, signals, retries. On Temporal it is a workflow.

```python
# <app>/jobs.py
from apps.flows.declare import job


@job("reports.nightly", schedule="30 2 * * *")  # 5-field cron, UTC
def nightly() -> dict:
    """Build the nightly report."""
    return {"built": 1}
```

```python
# <app>/workflows.py   - runs in Temporal's sandbox: NO Django models here
from temporalio import workflow
from apps.flows.declare import flow


@flow("orders.fulfil", input=FulfilInput, local=fulfil_local)
class Fulfil:
    """Reserve stock, wait for payment, ship."""

    @workflow.run
    async def run(self, data: FulfilInput) -> dict: ...
```

Workflows call work through activities (`@activity`, in `<app>/activities.py`) that call actions
or services; only activities touch the ORM. Arguments are ids, not personal data.

## With and without Temporal

| | `TEMPORAL_ENABLED=true` | `TEMPORAL_ENABLED=false` |
|---|---|---|
| Jobs | Temporal Schedules (`manage.py flows_sync`) | `manage.py run_scheduler` (one replica) or cron + `manage.py run_job NAME` |
| Flows | Workflow on the worker (`manage.py flows_worker`) | The flow's `local` function, inline |
| `django.tasks` | `TemporalTaskBackend` | `ImmediateBackend` |

A flow without a `local` function is Temporal-only; starting it with Temporal off raises
`FlowsDisabled`. The honest comparison of what each engine does is generated in
[Flow engines](../reference/engines.md).

## Starting flows

`flows.start(name, input)` from code, `POST /api/v1/actions/flows.start/` over HTTP/MCP (flows
must be declared `startable=True`). Identity (`organization_id`, `actor_id`) is stamped by the
engine from the caller; input that contains those keys is rejected.

## Safety defaults

- Payloads in Temporal history are encrypted (`TEMPORAL_PAYLOAD_ENCRYPTION`, AES-GCM).
- Context (request id, organization, actor, trace) travels client → workflow → activity.
- Changing a running workflow needs `workflow.patched`; keep golden replay histories in tests.
- Run `manage.py flows_sync` after deploys (creates/updates Schedules; `--prune` removes orphans).
