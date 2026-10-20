# OpenAPI, drf-spectacular, and Swagger

[Versão em português](../../pt-BR/tecnologias/openapi-swagger.md) ·
[Back to the learning path](../learning-path.md)

## What are they?

**OpenAPI** describes routes, methods, parameters, authentication, bodies, and responses.
**drf-spectacular** generates the schema from DRF. **Swagger UI** renders an interactive interface.

```text
Views + serializers → drf-spectacular → openapi-schema.yml → Swagger/clients
```

## Why does it matter?

Without a contract, frontend and backend depend on memory and messages. OpenAPI helps people
discover endpoints, lets CI validate the schema, supports generated clients, reveals breaking
changes, and centralizes examples and error codes.

## A schema is not security

Documenting `401` does not add authentication. Every endpoint still needs authentication,
permission, serialization, throttling, and tenant scope.

Never put tokens or real data in examples. The interactive UI is disabled by default in
production to reduce unnecessary exposure.

## Good practices

- describe actual requests and responses;
- document headers such as `X-Organization-ID`;
- include important status codes;
- use stable names and versions;
- validate the schema in CI;
- review schema changes like code;
- use synthetic examples.

The `/api/v1/` prefix allows a future incompatible version without immediately breaking clients.
Use Swagger for exploration and the OpenAPI file as the automated contract.
