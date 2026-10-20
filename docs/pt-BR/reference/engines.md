# Motores de fluxo

> Gerado por `python scripts/gen_docs.py`. Não edite à mão.

| Capacidade | Motor local | Temporal |
|---|---|---|
| Start a flow and read its result | sim | sim |
| Run on the caller's thread vs. in a worker process | inline | worker |
| Automatic retries with backoff | não | sim |
| Survives a process restart mid-flow | não | sim |
| Durable timers and sleeps (hours to months) | não | sim |
| Signals to a running flow | não | sim |
| Queries, child workflows, continue-as-new | não | sim |
| Cancel a running flow | não | sim |
| Scheduled jobs | manage.py run_scheduler (one replica) or cron + run_job | Temporal Schedules |
| Visibility UI and history | não | sim |
