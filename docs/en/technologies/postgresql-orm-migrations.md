# PostgreSQL, ORM, and migrations

[Versão em português](../../pt-BR/tecnologias/postgresql-orm-migrations.md) ·
[Back to the learning path](../learning-path.md)

## What are they?

**PostgreSQL** is the main database for data that must survive. **psycopg** lets Python communicate
with it. Django's **ORM** turns Python operations into SQL.

```python
Invoice.objects.filter(
    organization=request.organization,
    status="open",
)
```

## Why are they here?

A SaaS needs transactions, constraints, indexes, and reliable queries. SQLite is convenient for
small local development, but production requires PostgreSQL.

- **Transaction:** multiple changes become an all-or-nothing operation.
- **Constraint:** the database rejects invalid states even when code fails.
- **Index:** accelerates a specific search.
- **Foreign key:** ensures a referenced record exists.

## Migrations

Models describe the desired shape; migrations describe how to reach it:

```powershell
python manage.py makemigrations
python manage.py migrate
```

Review migrations before deployment. Large changes may lock tables, so prefer compatible steps.
On Fly, `release_command` applies migrations before releasing the version.

## Security and tenants

The ORM reduces manual SQL but does not add tenant scope by itself. Every customer-data query must
use `request.organization`. Scope customer-specific uniqueness to the organization.

Use TLS, separate credentials per environment, encrypted backups, and restore tests. For high-risk
products, consider Row-Level Security as a second boundary.

## Scale and limits

`CONN_MAX_AGE` reuses connections. PgBouncer helps with many Machines and workers. Every worker
consumes memory and database connections, so increasing processes without measurements can
overload the database.

Indexes consume storage and make writes more expensive. Create them from real queries and plans.
Use PostgreSQL for persistent business state, not as an improvised file store or task queue.
