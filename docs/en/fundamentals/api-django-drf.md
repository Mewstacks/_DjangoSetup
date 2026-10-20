# API, Django, and DRF

[Versão em português](../../pt-BR/fundamentos/api-django-drf.md) ·
[Back to the summary](../technologies-and-middleware.md)

## API and endpoint

An API lets programs communicate. Each address and HTTP method combination is an endpoint:

| Method | Common use | Example |
| --- | --- | --- |
| `GET` | Read | List invoices |
| `POST` | Create | Create an invoice |
| `PATCH` | Partially update | Change a status |
| `DELETE` | Delete | Remove an invoice |

The status describes the result: `200` success, `201` created, `400` invalid input, `401` not
logged in, `403` not allowed, `404` not found, and `429` rate limit exceeded.

## Django's role

Django connects URLs, Python code, and the database. Its ORM lets you query the database without
writing SQL in most cases:

```python
Invoice.objects.filter(organization=request.organization)
```

A **migration** records a database change, such as creating a table or column. Changing only the
model does not change the database: generate and apply the migration.

## What DRF adds

Django REST Framework organizes an API into pieces:

```text
URL → View/ViewSet → Permission → Serializer → Model
```

- **View/ViewSet:** coordinates the action.
- **Serializer:** accepts only defined fields and formats.
- **Authentication:** identifies the user.
- **Permission:** authorizes the action.
- **Pagination:** divides large lists into pages.
- **Throttle:** reduces excessive requests.

A serializer prevents direct trust in JSON:

```python
class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ("id", "number", "amount_cents")
        read_only_fields = ("id",)
```

Fields absent from `fields` do not appear in the API. Product rules such as “a paid invoice cannot
be deleted” still require explicit validation.

## Authentication is not authorization

- **Authentication:** “who are you?”
- **Authorization:** “what may you do?”

A logged-in user should not automatically administer an organization. This is why permissions
such as `IsAuthenticated` and `IsOrganizationAdministrator` exist.

## Calling the API with Python

This project uses sessions and CSRF. `requests.Session()` preserves cookies:

```python
import requests

api = requests.Session()
base_url = "http://localhost:8000/api/v1"

csrf = api.get(f"{base_url}/auth/csrf/").json()["csrf_token"]
api.post(
    f"{base_url}/auth/login/",
    json={"email": "user@example.com", "password": "strong-password"},
    headers={"X-CSRFToken": csrf},
).raise_for_status()
csrf = api.get(f"{base_url}/auth/csrf/").json()["csrf_token"]

response = api.get(
    f"{base_url}/organizations/",
    headers={"X-Organization-ID": "organization-uuid"},
)
response.raise_for_status()
print(response.json())
```

Django rotates the token during login, so the example fetches it again. Send the current token for
`POST`, `PATCH`, `PUT`, and `DELETE` operations. CORS does not affect Python clients; browsers
enforce it.

## Common mistakes

- enforcing authorization only in the frontend;
- accepting fields the client should not control;
- returning lists without pagination;
- putting all logic inside a serializer or view;
- confusing `401` and `403`;
- changing models without migrations;
- exposing internal details in error messages.

## Next step

Read [tenants and isolation](tenants-and-isolation.md) before creating company-owned data. Then
follow the [adding a resource](../adding-a-resource.md) recipe.
