# Adicionar um fluxo ou job

- **Job** é uma função executada uma vez, opcionalmente em cron (limpezas, varreduras, lembretes).
- **Fluxo** é um processo durável: espera dias, recebe sinais, tenta de novo. No Temporal é um
  workflow.

```python
# <app>/jobs.py
from apps.flows.declare import job


@job("reports.nightly", schedule="30 2 * * *")  # cron de 5 campos, UTC
def nightly() -> dict:
    """Gera o relatório noturno."""
    return {"built": 1}
```

```python
# <app>/workflows.py   - roda no sandbox do Temporal: SEM models do Django aqui
from temporalio import workflow
from apps.flows.declare import flow


@flow("orders.fulfil", input=FulfilInput, local=fulfil_local)
class Fulfil:
    """Reserva estoque, espera o pagamento, envia."""

    @workflow.run
    async def run(self, data: FulfilInput) -> dict: ...
```

Workflows chamam o trabalho por activities (`@activity`, em `<app>/activities.py`) que chamam
ações ou serviços; só activities tocam o ORM. Argumentos são ids, não dados pessoais.

## Com e sem Temporal

| | `TEMPORAL_ENABLED=true` | `TEMPORAL_ENABLED=false` |
|---|---|---|
| Jobs | Temporal Schedules (`manage.py flows_sync`) | `manage.py run_scheduler` (uma réplica) ou cron + `manage.py run_job NOME` |
| Fluxos | Workflow no worker (`manage.py flows_worker`) | A função `local` do fluxo, inline |
| `django.tasks` | `TemporalTaskBackend` | `ImmediateBackend` |

Um fluxo sem função `local` é só-Temporal; iniciá-lo com Temporal desligado levanta
`FlowsDisabled`. A comparação honesta do que cada motor faz está gerada em
[Motores de fluxo](../reference/engines.md).

## Iniciando fluxos

`flows.start(nome, entrada)` em código, `POST /api/v1/actions/flows.start/` por HTTP/MCP (o fluxo
precisa de `startable=True`). A identidade (`organization_id`, `actor_id`) é carimbada pelo motor
a partir de quem chama; entrada com essas chaves é rejeitada.

## Padrões seguros

- Payloads no histórico do Temporal são cifrados (`TEMPORAL_PAYLOAD_ENCRYPTION`, AES-GCM), e um
  payload **não selado** é recusado: a chave também é o que prova que a entrada de uma activity veio
  deste deployment. A produção não inicia com Temporal ligado sem TLS, chave de API ou
  `TEMPORAL_ALLOW_INSECURE` explícito. Esvaziar histórico gravado antes da cifragem exige o
  `TEMPORAL_ALLOW_PLAINTEXT_PAYLOADS=true` temporário.
- A ponte de tarefas (`django.tasks` no Temporal) roda só tarefas declaradas sob
  `FLOWS_TASK_MODULE_PREFIXES` (padrão `apps.`).
- Um flow roda como a pessoa que o iniciou, com o papel dela, mas não com os escopos da credencial
  que o iniciou: declare o `scope` do flow para cobrir tudo o que ele faz.
- O contexto (request id, organização, ator, trace) viaja cliente → workflow → activity.
- Mudar um workflow em execução exige `workflow.patched`; mantenha históricos de replay nos testes.
- Rode `manage.py flows_sync` após cada deploy (cria/atualiza Schedules; `--prune` remove órfãos).
