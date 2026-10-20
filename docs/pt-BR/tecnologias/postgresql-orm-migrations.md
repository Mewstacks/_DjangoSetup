# PostgreSQL, ORM e migrations

[English version](../../en/technologies/postgresql-orm-migrations.md) ·
[Voltar à trilha](../trilha-aprendizado.md)

## O que são?

**PostgreSQL** é o banco principal: guarda dados que precisam sobreviver. **psycopg** é o driver
que permite ao Python conversar com ele. O **ORM do Django** transforma operações Python em SQL.

```python
Invoice.objects.filter(
    organization=request.organization,
    status="open",
)
```

## Por que estão no projeto?

Um SaaS precisa de transações, constraints, índices e consultas confiáveis. SQLite é conveniente
para desenvolvimento pequeno, mas produção exige PostgreSQL.

- **Transaction:** várias alterações viram uma única operação de “tudo ou nada”.
- **Constraint:** o banco rejeita estados inválidos, mesmo se o código errar.
- **Index:** acelera uma busca específica.
- **Foreign key:** garante que uma referência realmente exista.

## Migrations

Models descrevem o formato desejado; migrations descrevem como chegar até ele:

```powershell
python manage.py makemigrations
python manage.py migrate
```

Revise migrations antes do deploy. Alterações grandes podem bloquear tabelas; prefira mudanças
compatíveis em etapas. No Fly, o `release_command` aplica migrations antes de liberar a versão.

## Segurança e tenants

O ORM reduz SQL manual, mas não adiciona escopo de tenant sozinho. Toda consulta de dados de
clientes precisa usar `request.organization`.

Constraints devem incluir a organização quando a unicidade for por cliente:

```python
models.UniqueConstraint(
    fields=("organization", "number"),
    name="unique_invoice_number_per_org",
)
```

Use TLS na conexão, credenciais separadas por ambiente, backups criptografados e testes de
restauração. Para alto risco, avalie Row-Level Security como segunda barreira.

## Escala e limites

`CONN_MAX_AGE` reutiliza conexões. PgBouncer ajuda quando existem muitas Machines/workers. Cada
worker consome memória e conexões, então aumentar processos sem medir pode derrubar o banco.

Índices não são gratuitos: ocupam espaço e tornam escritas mais caras. Crie-os a partir de queries
e planos reais, não por adivinhação.

## Use para

Usuários, organizações, pagamentos, consentimentos, auditoria e estado de jobs. Não use PostgreSQL
como fila improvisada ou para servir arquivos grandes quando Redis, Celery ou object storage forem
mais adequados.
