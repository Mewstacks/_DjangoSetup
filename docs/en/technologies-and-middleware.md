# Backend in 5 minutes

[Versão em português](../pt-BR/tecnologias-e-middlewares.md)

This is the starting point. Follow the links for deeper explanations.

## What happens here?

The **frontend** displays the interface. The **backend** receives requests, checks rules, and
accesses data. An **API** is the set of addresses, called endpoints, used to talk to the backend.

```text
Python client → HTTPS → Django/DRF → product rule → database → JSON response
```

For example:

```text
GET  /api/v1/invoices/  → list invoices
POST /api/v1/invoices/  → create an invoice
```

## Essential words

| Term | Simple meaning |
| --- | --- |
| Django | Python framework that provides the backend structure |
| DRF | Django REST Framework, used to create JSON APIs |
| Serializer | Validates incoming JSON and controls outgoing JSON |
| Permission | Decides whether a user may perform an action |
| Middleware | Common layer executed before/after views |
| Tenant | Each customer or company inside the same SaaS |
| PostgreSQL | Database for permanent data |
| Redis | Fast storage for cache, sessions, and queues |
| Celery | Runs slow work in the background |
| Sentry | Reports and helps investigate errors |

## What is a tenant?

A tenant is one company using the SaaS:

```text
Same system and database
├── Company A → sees only its data
└── Company B → sees only its data
```

In this project, `Organization` represents the tenant. The backend validates
`X-Organization-ID` and creates `request.organization`. Every customer-data query must use that
organization.

## Security in layers

- HTTPS protects data in transit.
- Sessions and authentication identify the user.
- Permissions control actions.
- Tenant isolation separates companies.
- Serializers reject invalid input.
- Argon2 protects password hashes.
- AES-GCM encrypts especially sensitive fields.
- Axes and throttling reduce abuse.
- Logs and Sentry support investigation without retaining personal data.

No layer solves everything. LGPD also requires decisions about purpose, lawful basis, retention,
vendors, data subject rights, and incidents.

## Continue by topic

See the [complete learning path](learning-path.md), which covers most installed technologies. To
get started:

1. [API, Django, and DRF](fundamentals/api-django-drf.md): endpoints, views, serializers,
   permissions, and Python clients.
2. [Tenants and isolation](fundamentals/tenants-and-isolation.md): preventing leaks between
   companies.
3. [Middleware and security](fundamentals/middleware-and-security.md): why each middleware exists.
4. [Data, jobs, and observability](fundamentals/data-jobs-observability.md): PostgreSQL, Redis,
   Celery, files, and Sentry.
5. [Adding a resource](adding-a-resource.md): a practical recipe for implementing an API.
6. [Security model](security.md) and [LGPD guide](lgpd.md): production decisions.

Start with the request path. At each layer, ask: **who is requesting, may they do this, and which
data may they see?**
