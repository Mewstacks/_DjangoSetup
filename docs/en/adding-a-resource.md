# Adding a resource

[Versão em português](../pt-BR/adicionando-um-recurso.md)

Every tenant resource follows the same four steps. Nothing here is optional and nothing
else is required: authentication, throttling, audit context, and tenant scoping already
apply to anything registered this way.

## 1. Model

Inherit `OrganizationScopedModel`. It supplies the UUID primary key, timestamps, the
`organization` foreign key, and the `(organization, created_at)` index.

```python
# src/apps/invoices/models.py
from django.db import models

from apps.organizations.models import OrganizationScopedModel


class Invoice(OrganizationScopedModel):
    number = models.CharField(max_length=32)
    amount_cents = models.PositiveIntegerField()

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("organization", "number"), name="unique_invoice_number")
        ]
```

Scope uniqueness to the organization, never globally, or one tenant can block a number
another tenant wants to use.

## 2. Serializer

Leave `organization` out of `fields`. The viewset assigns it from the request, so a client
cannot write into another tenant by sending an ID.

```python
# src/apps/invoices/api.py
from rest_framework import serializers

from apps.invoices.models import Invoice


class InvoiceSerializer(serializers.ModelSerializer[Invoice]):
    class Meta:
        model = Invoice
        fields = ("id", "number", "amount_cents", "created_at")
        read_only_fields = ("id", "created_at")
```

## 3. Viewset

Inherit `OrganizationScopedViewSet` and set two attributes. The tenant filter and the
`organization` assignment on create come from the base class.

```python
from apps.organizations.viewsets import OrganizationScopedViewSet


class InvoiceViewSet(OrganizationScopedViewSet[Invoice]):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
```

Restrict verbs with `http_method_names`, and require an admin role by swapping the
permission:

```python
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
```

## 4. Route

```python
# src/config/urls_api.py
router.register("invoices", InvoiceViewSet, basename="invoice")
```

Add the app to `LOCAL_APPS` in `src/config/settings/base.py`, then run
`python manage.py makemigrations invoices`.

## Tests

`tests/conftest.py` provides `org_client` (logged in, organization already selected) and
`other_org_client` (a second tenant). A resource needs one happy-path test; cross-tenant
leakage is swept automatically for every registered scoped route by
`tests/test_tenant_isolation.py`.

```python
@pytest.mark.django_db
def test_invoices_are_listed_for_the_selected_organization(org_client, organization):
    Invoice.objects.create(organization=organization, number="0001", amount_cents=1000)
    response = org_client.get("/api/v1/invoices/")
    assert response.status_code == 200
    assert response.data["results"][0]["number"] == "0001"
```

## Recording an audit event

Pass the request so the hashed IP is stored with the event.

```python
from apps.audit.services import record_event

record_event(
    action="invoice.issued",
    actor=request.user,
    organization=request.organization,
    target=invoice,
    request=request,
)
```

Metadata is rejected if it contains personal-data keys; see
[the security model](security.md).

## Background work

Put anything slower than a request in Celery. Tasks are auto-discovered from
`tasks.py` inside each app.

```python
# src/apps/invoices/tasks.py
from celery import shared_task


@shared_task
def send_invoice(invoice_id: str) -> None: ...
```
