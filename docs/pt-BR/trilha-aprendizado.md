# Trilha de aprendizado da stack

[English version](../en/learning-path.md) ·
[Voltar ao resumo](tecnologias-e-middlewares.md)

Leia na ordem que fizer sentido. Cada guia explica a importância, o uso real, a segurança e os
limites da tecnologia.

## 1. Fundamentos

| Tema | Tecnologias | Guia |
| --- | --- | --- |
| Backend e APIs | HTTP, JSON, Python, Django e DRF | [API, Django e DRF](fundamentos/api-django-drf.md) |
| SaaS compartilhado | Organization, Membership e escopo | [Tenants e isolamento](fundamentos/tenants-e-isolamento.md) |
| Pipeline HTTP | Middlewares, CORS, CSRF, CSP e Axes | [Middlewares e segurança](fundamentos/middlewares-e-seguranca.md) |

## 2. Dados e processamento

| Tema | Tecnologias | Guia |
| --- | --- | --- |
| Banco principal | PostgreSQL, psycopg, ORM e migrations | [PostgreSQL, ORM e migrations](tecnologias/postgresql-orm-migrations.md) |
| Dados temporários | Redis, cache, sessão e rate limit | [Redis, cache e sessões](tecnologias/redis-cache-sessoes.md) |
| Trabalho assíncrono | Celery, broker, worker e idempotência | [Celery e jobs](tecnologias/celery-jobs.md) |
| Arquivos | Tigris/S3, django-storages e URLs assinadas | [Object storage](tecnologias/object-storage.md) |

## 3. Segurança e privacidade

| Tema | Tecnologias | Guia |
| --- | --- | --- |
| Proteção de dados | Argon2, AES-GCM, HMAC e gestão de chaves | [Criptografia, senhas e segredos](tecnologias/criptografia-senhas-segredos.md) |
| Controles técnicos | Cookies, headers, throttling e auditoria | [Modelo de segurança](seguranca.md) |
| Programa de privacidade | LGPD, retenção e direitos | [Guia LGPD](lgpd.md) |

## 4. Execução e deploy

| Tema | Tecnologias | Guia |
| --- | --- | --- |
| Servidor e hospedagem | ASGI, Gunicorn, Uvicorn, Docker e Fly.io | [Runtime, Docker e Fly](tecnologias/runtime-docker-fly.md) |
| Operação | Sentry, logs JSON, request ID e health checks | [Sentry, logs e health checks](tecnologias/sentry-logs-health.md) |

## 5. Contrato e qualidade

| Tema | Tecnologias | Guia |
| --- | --- | --- |
| Contrato da API | OpenAPI, drf-spectacular e Swagger | [OpenAPI e Swagger](tecnologias/openapi-swagger.md) |
| Qualidade | pytest, coverage, Ruff, mypy, pip-audit e CI | [Testes, qualidade e CI](tecnologias/testes-qualidade-ci.md) |

## Ordem recomendada

Para construir endpoints, leia fundamentos → PostgreSQL → tenants → testes. Para publicar, leia
runtime → Redis → Celery → observabilidade. Antes de dados reais, leia segurança → criptografia →
LGPD → runbooks.

Não é preciso dominar tudo antes de começar. Aprenda uma camada, use-a num exemplo pequeno e
escreva um teste antes de seguir.
