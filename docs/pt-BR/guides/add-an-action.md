# Adicionar uma ação

Uma ação é uma função `fn(ctx, data) -> resultado` com entrada e saída pydantic. Declará-la com
`@action` registra o contrato (nome, escopo, se escreve) e nada mais: REST, MCP, a CLI e o Temporal
são adaptadores sobre o registro, então uma função são quatro integrações.

**Caminho mais rápido:** `python manage.py scaffold resource invoices Invoice --fields 'title:str,amount:decimal'`
gera um recurso completo que já segue todas as regras desta página (veja
[Comece um produto](start-a-product.md)). Continue lendo para entender, ou para adicionar uma ação a um
app existente.

```python
# <app>/actions.py  (descoberto automaticamente)
from pydantic import BaseModel
from apps.actions.context import ActionContext
from apps.actions.registry import action


class CreateTask(BaseModel):
    title: str


class TaskOut(BaseModel):
    id: str
    title: str


@action("tasks.create", write=True, undoable=True)
def create_task(ctx: ActionContext, data: CreateTask) -> TaskOut:
    """Cria uma tarefa na organização de quem chama. Envie Idempotency-Key para repetir com segurança."""
    task = services.create_task(ctx, title=data.title)  # regras de negócio ficam em services.py
    return TaskOut(id=str(task.id), title=task.title)
```

Regras checadas quando o app inicia (falham na partida, não em produção):

- o nome é `dominio.verbo` e único;
- o docstring não é vazio: é o que um modelo lê como descrição da ferramenta;
- o escopo de uma ação de escrita não é um escopo `:read`;
- **uma ação de escrita diz se pode ser desfeita**: `undoable=True` (com um handler, veja abaixo) ou
  `undoable="<por que não pode>"`;
- `data` e o retorno são modelos pydantic.

Opções: `scope=`, `write=`, `channels={"api","mcp","flow","cli"}`, `roles=`, `idempotent=`,
`destructive=` (dica MCP), `audit=`, `undoable=`, `title=`.

## Checklist para um recurso novo

1. Modelo: herde de `OrganizationScopedModel`.
2. `<app>/privacy.py`: `personal(...)` ou `not_personal(..., motivo)`. A suíte de testes falha caso
   contrário, e também quando um campo de cara pessoal não está listado ou um sensível não é cifrado.
3. Leia por `ctx.scoped(Model)` ou `ctx.get(Model, id)`; nunca `Model.objects` dentro de ações.
4. Emita um evento se terceiros se importam: `register_event` em `<app>/events.py` e
   `emit("task.created", org, {"task_id": ...})` dentro da mesma transação.
5. Registre mudanças para o desfazer: `ctx.record_change(...)` e `ctx.set_target(row)` no serviço.
6. Regenere os artefatos versionados: `python manage.py actions_catalog`,
   `python scripts/check_openapi.py --write`, `python scripts/gen_docs.py`.
7. Teste. A suíte de conformidade já checa escopo, papéis somente leitura, canais não listados e
   entrada inválida para **toda** ação; adicione os casos entre tenants e de negócio.

## Desfazer

`undoable=True` significa que um handler de desfazer reverte a mudança, para que agentes possam
desfazer o próprio trabalho (`actions.changes`, `actions.undo`). Coloque os handlers em
`<app>/undo.py` (descoberto automaticamente): o diário guarda snapshots antes/depois cifrados e recusa
um desfazer quando a linha foi editada depois. Veja `apps/examples/undo.py`. Ações que não podem ser
desfeitas dão o motivo como valor de `undoable` (por exemplo "um sinal entregue não pode ser
recolhido").

## Escopos

Um escopo é `dominio:nivel`. Os novos aparecem no catálogo automaticamente; escopos extras sem ações
vêm de `ACTIONS_EXTRA_SCOPES`. O mesmo vocabulário de escopos serve chaves de API, consentimento OAuth e
MCP. Veja [papéis e permissões](roles-and-permissions.md).

## Removendo o exemplo

`python scripts/remove_example.py` apaga `apps/examples`, o desliga e lista os testes que ainda usam
Notes, que você porta para o seu recurso.
