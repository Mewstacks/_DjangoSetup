# API, Django e DRF

[English version](../../en/fundamentals/api-django-drf.md) ·
[Voltar ao resumo](../tecnologias-e-middlewares.md)

## API e endpoint

Uma API permite que programas conversem. Cada combinação de endereço e método é um endpoint:

| Método | Uso comum | Exemplo |
| --- | --- | --- |
| `GET` | Ler | Listar faturas |
| `POST` | Criar | Criar fatura |
| `PATCH` | Alterar parte | Mudar status |
| `DELETE` | Excluir | Remover fatura |

O status explica o resultado: `200` sucesso, `201` criado, `400` entrada inválida, `401` sem
login, `403` sem permissão, `404` não encontrado e `429` limite excedido.

## O papel do Django

Django conecta URL, código Python e banco. Seu ORM permite consultar o banco sem escrever SQL na
maioria dos casos:

```python
Invoice.objects.filter(organization=request.organization)
```

Uma **migration** registra mudanças no banco, como criar uma tabela ou coluna. Alterar somente o
model não altera o banco: gere e aplique a migration.

## O que o DRF adiciona

O Django REST Framework organiza a API em peças:

```text
URL → View/ViewSet → Permission → Serializer → Model
```

- **View/ViewSet:** coordena a ação.
- **Serializer:** aceita apenas campos e formatos definidos.
- **Authentication:** identifica o usuário.
- **Permission:** autoriza a ação.
- **Pagination:** divide listas grandes em páginas.
- **Throttle:** reduz excesso de requisições.

Um serializer evita confiar diretamente no JSON:

```python
class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ("id", "number", "amount_cents")
        read_only_fields = ("id",)
```

Campos ausentes de `fields` não aparecem na API. Regras do produto, como “fatura paga não pode
ser apagada”, ainda precisam de validação explícita.

## Autenticação não é autorização

- **Autenticação:** “quem é você?”
- **Autorização:** “o que você pode fazer?”

Um usuário logado não deve automaticamente administrar uma organização. Por isso existem
permissions como `IsAuthenticated` e `IsOrganizationAdministrator`.

## Consumindo com Python

Este projeto usa sessão e CSRF. `requests.Session()` preserva cookies:

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

O Django troca o token durante o login, por isso o exemplo o busca novamente. Em operações
`POST`, `PATCH`, `PUT` e `DELETE`, envie o token atual. CORS não afeta clientes Python; ele é uma
proteção aplicada por navegadores.

## Erros comuns

- colocar regra de autorização apenas no frontend;
- aceitar campos que o cliente não deveria controlar;
- retornar listas sem paginação;
- esconder toda lógica dentro do serializer ou da view;
- confundir `401` com `403`;
- alterar models sem migrations;
- expor detalhes internos em mensagens de erro.

## Próximo passo

Leia [tenants e isolamento](tenants-e-isolamento.md) antes de criar dados pertencentes a uma
empresa. Depois siga a receita [adicionando um recurso](../adicionando-um-recurso.md).
