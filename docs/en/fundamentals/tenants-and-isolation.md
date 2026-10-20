# Tenants and data isolation

[Versão em português](../../pt-BR/fundamentos/tenants-e-isolamento.md) ·
[Back to the summary](../technologies-and-middleware.md)

## What is a tenant?

A tenant is each customer sharing the application:

```text
Shared database
├── Organization A → invoices A
└── Organization B → invoices B
```

Isolation must prevent A from reading, changing, deleting, or even discovering B's data.

## How this project selects a tenant

1. The client sends `X-Organization-ID`.
2. `AuthenticationMiddleware` identifies `request.user`.
3. `OrganizationContextMiddleware` finds an active link between user and organization.
4. If none exists, it returns `404`.
5. Otherwise, it sets `request.organization` and `request.organization_membership`.

The header is only a selection request. It is never proof of access.

## Model and viewset

Company-owned data inherits `OrganizationScopedModel`:

```python
class Invoice(OrganizationScopedModel):
    number = models.CharField(max_length=32)
```

The base viewset filters reads and assigns the organization on create:

```python
class InvoiceViewSet(OrganizationScopedViewSet[Invoice]):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
```

Leave `organization` out of the serializer. Do not override `get_queryset()` or `perform_create()`
without preserving the scope.

## Relationships also need scope

Filtering only the main object is insufficient. If an invoice accepts `project_id`, confirm that
the project belongs to `request.organization`:

```python
project = Project.objects.get(
    id=project_id,
    organization=request.organization,
)
```

Otherwise, organization A could create a record related to something owned by organization B.

## Permissions and roles

A membership provides a role such as `owner`, `admin`, or `member`. Define permissions from real
actions:

- may a member view?
- may an administrator invite?
- may an auditor modify?
- may an owner delete the organization?

Hiding a frontend button does not protect an API. The permission must exist in the backend.

## How to test correctly

Create:

- two organizations;
- one user who belongs to both;
- one record in each organization.

Select A and verify that B's record cannot be listed, retrieved, changed, or deleted. Also test
creation with related IDs from B. A test with only an unrelated user verifies middleware, but does
not prove query scoping.

## Limits

The base class reduces mistakes, but custom code can bypass it. Celery tasks, scripts, Admin, and
maintenance commands must also receive the organization explicitly.

For high-risk products, PostgreSQL Row-Level Security can add a second barrier. It needs careful
design for migrations, Admin, and workers.

## Practical rule

Whenever a model contains customer data, ask:

1. does it have an `organization`?
2. do all reads use that organization?
3. do creates and updates prevent tenant changes?
4. do relationships belong to the same tenant?
5. do tests attempt to cross the boundary?
