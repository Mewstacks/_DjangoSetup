# Adicionando um recurso

[English version](../en/adding-a-resource.md)

Todo recurso de tenant segue os mesmos quatro passos. Nada aqui é opcional e nada além
disso é necessário: autenticação, throttling, contexto de auditoria e isolamento por
organização já valem para qualquer coisa registrada assim.

## 1. Model

Herde `OrganizationScopedModel`. Ele já traz chave primária UUID, timestamps, a foreign key
`organization` e o índice `(organization, created_at)`.

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

Restrinja unicidade à organização, nunca global, ou um tenant bloqueia um número que outro
tenant quer usar.

## 2. Serializer

Deixe `organization` fora de `fields`. O viewset atribui a partir do request, então o
cliente não consegue escrever em outro tenant mandando um ID.

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

Herde `OrganizationScopedViewSet` e defina dois atributos. O filtro por tenant e a
atribuição de `organization` na criação vêm da classe base.

```python
from apps.organizations.viewsets import OrganizationScopedViewSet


class InvoiceViewSet(OrganizationScopedViewSet[Invoice]):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
```

Limite os verbos com `http_method_names` e exija papel de administrador trocando a
permissão:

```python
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
```

## 4. Rota

```python
# src/config/urls_api.py
router.register("invoices", InvoiceViewSet, basename="invoice")
```

Adicione o app em `LOCAL_APPS` no `src/config/settings/base.py` e rode
`python manage.py makemigrations invoices`.

## Testes

O `tests/conftest.py` fornece `org_client` (logado e com organização já selecionada) e
`other_org_client` (um segundo tenant). Cada recurso precisa de um teste de caminho feliz;
vazamento entre tenants é varrido automaticamente para toda rota escopada registrada pelo
`tests/test_tenant_isolation.py`.

```python
@pytest.mark.django_db
def test_invoices_are_listed_for_the_selected_organization(org_client, organization):
    Invoice.objects.create(organization=organization, number="0001", amount_cents=1000)
    response = org_client.get("/api/v1/invoices/")
    assert response.status_code == 200
    assert response.data["results"][0]["number"] == "0001"
```

## Registrando um evento de auditoria

Passe o request para que o IP com hash seja gravado junto.

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

Metadados com chaves de dados pessoais são rejeitados; veja
[o modelo de segurança](seguranca.md).

## Trabalho em background

Coloque no Celery qualquer coisa mais lenta que um request. As tasks são descobertas
automaticamente em `tasks.py` dentro de cada app.

```python
# src/apps/invoices/tasks.py
from celery import shared_task


@shared_task
def send_invoice(invoice_id: str) -> None: ...
```
