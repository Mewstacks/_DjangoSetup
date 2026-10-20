# Tenants e isolamento de dados

[English version](../../en/fundamentals/tenants-and-isolation.md) ·
[Voltar ao resumo](../tecnologias-e-middlewares.md)

## O que é tenant?

Tenant é cada cliente que compartilha a aplicação:

```text
Banco compartilhado
├── Organization A → invoices A
└── Organization B → invoices B
```

O objetivo do isolamento é impedir que A leia, altere, apague ou até descubra dados de B.

## Como este projeto seleciona o tenant

1. O cliente envia `X-Organization-ID`.
2. `AuthenticationMiddleware` identifica `request.user`.
3. `OrganizationContextMiddleware` procura uma associação ativa entre usuário e organização.
4. Se não encontrar, responde `404`.
5. Se encontrar, define `request.organization` e `request.organization_membership`.

O header é apenas um pedido de seleção. Ele nunca é prova de acesso.

## Model e viewset

Um dado pertencente a uma empresa herda `OrganizationScopedModel`:

```python
class Invoice(OrganizationScopedModel):
    number = models.CharField(max_length=32)
```

O viewset-base filtra leituras e atribui a organização na criação:

```python
class InvoiceViewSet(OrganizationScopedViewSet[Invoice]):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
```

Deixe `organization` fora do serializer. Também não sobrescreva `get_queryset()` ou
`perform_create()` sem manter o escopo.

## Relacionamentos também precisam de escopo

Filtrar somente o objeto principal não basta. Se uma fatura recebe `project_id`, confirme que o
projeto pertence a `request.organization`:

```python
project = Project.objects.get(
    id=project_id,
    organization=request.organization,
)
```

Sem isso, a organização A poderia criar um registro relacionado a algo da organização B.

## Permissions e papéis

Membership informa o papel do usuário, como `owner`, `admin` ou `member`. Defina permissões pela
ação real:

- membro pode visualizar?
- administrador pode convidar?
- auditor pode alterar?
- proprietário pode excluir a organização?

Ocultar um botão no frontend não protege a API. A permission precisa existir no backend.

## Como testar corretamente

Crie:

- duas organizações;
- um usuário membro das duas;
- um registro em cada organização.

Selecione A e teste que não é possível listar, consultar, alterar ou apagar o registro de B.
Teste também criação com IDs relacionados de B. Um teste apenas com usuário estranho verifica o
middleware, mas não prova que a query está escopada.

## Limites

A classe-base reduz erros, mas código customizado pode contorná-la. Jobs Celery, scripts, Admin e
comandos de manutenção também precisam receber a organização explicitamente.

Para produtos de risco elevado, PostgreSQL Row-Level Security pode adicionar uma segunda
barreira. Ela exige projeto cuidadoso para migrations, Admin e workers.

## Regra prática

Sempre que um model tiver dados de cliente, pergunte:

1. ele possui `organization`?
2. todas as leituras usam essa organização?
3. criação e alteração impedem troca de tenant?
4. relacionamentos pertencem ao mesmo tenant?
5. os testes tentam atravessar a fronteira?
