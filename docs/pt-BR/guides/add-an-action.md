# Adicionar uma ação

Uma ação é uma função `fn(ctx, data) -> resultado` com entrada e saída pydantic. Declará-la cria,
sem mais código, `POST /api/v1/actions/<nome>/`, uma ferramenta MCP, uma activity do Temporal e
um comando de CLI, todos sob as mesmas regras de escopo, papel, rate limit, idempotência e
auditoria.

```python
# src/apps/tasks/actions.py   (qualquer app instalado; módulos actions.py são descobertos)
from pydantic import BaseModel, Field
from apps.actions.context import ActionContext
from apps.actions.registry import action
from apps.tasks.models import Task


class CreateTask(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class TaskOut(BaseModel):
    id: str
    title: str


@action("tasks.create", write=True)
def create_task(ctx: ActionContext, data: CreateTask) -> TaskOut:
    """Cria uma tarefa na organização atual."""  # este texto é a descrição da tool MCP
    task = Task.objects.create(organization=ctx.organization, title=data.title)
    return TaskOut(id=str(task.id), title=task.title)
```

Regras checadas na inicialização: nome `dominio.verbo` e único; docstring não vazia; ação de
escrita não usa escopo `:read`; entrada e saída são modelos pydantic. Opções: `scope=`,
`write=`, `channels={"api","mcp","flow","cli"}`, `roles=`, `idempotent=`, `destructive=`
(dica MCP), `undo=` (veja abaixo).

## Checklist de um novo recurso

1. Model: herde de `OrganizationScopedModel`.
2. `<app>/privacy.py`: `personal(...)` ou `not_personal(..., motivo)`. A suíte falha sem isso.
3. Leia por `ctx.scoped(Model)` ou `ctx.get(Model, id)`; nunca `Model.objects` dentro de ações.
4. Emita um evento se terceiros se importam: `register_event` em `<app>/events.py` e
   `emit("task.created", org, {"task_id": ...})` na mesma transação.
5. Regenere os artefatos versionados: `python manage.py actions_catalog`,
   `python scripts/check_openapi.py --write`, `python scripts/gen_docs.py`.
6. Teste com o API client; o teste da matriz de auth cobre o escopo da nova ação.

## Undo

Passe um handler de undo para que agentes desfaçam as próprias mudanças (`actions.changes`,
`actions.undo`). O journal guarda snapshots antes/depois cifrados e recusa o undo se a linha foi
editada depois. Veja `apps/examples/undo.py`.

## Escopos

Escopo é `dominio:nivel`. Os novos aparecem no catálogo sozinhos; escopos extras sem ações vêm de
`ACTIONS_EXTRA_SCOPES`. O mesmo vocabulário serve para chaves de API, consentimento OAuth e MCP.

Remover o exemplo: apague `apps/examples`, a entrada em `LOCAL_APPS`, seus testes e rode os
geradores de novo.
