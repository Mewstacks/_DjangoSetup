# Guia rápido de uso

[English version](README.en.md) · [Índice da documentação](docs/README.md)

Este projeto é uma base reutilizável para backends SaaS em Django. Ele já oferece autenticação,
API REST, organizações, controles técnicos para LGPD, criptografia, auditoria, tarefas
assíncronas, Sentry e configuração para Fly.io.

> Os controles do projeto ajudam na segurança e na geração de evidências, mas não tornam um
> produto automaticamente adequado à LGPD. Cada SaaS ainda precisa definir finalidades, bases
> legais, retenção, fornecedores, avisos de privacidade e responsáveis.

## 1. Iniciar localmente

Requer Python 3.12. Para iniciar rapidamente com SQLite:

```powershell
python -m pip install uv==0.12.0
uv sync --locked --all-extras
.\.venv\Scripts\Activate.ps1
python scripts/init_local.py --sqlite
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Endereços locais:

- API: `http://127.0.0.1:8000/api/v1/`
- Swagger: `http://127.0.0.1:8000/api/docs/`
- Admin: `http://127.0.0.1:8000/admin/`

Swagger e Django Admin ficam desabilitados por padrão em produção.

Para usar PostgreSQL e Redis localmente, instale o Docker, execute
`python scripts/init_local.py` sem `--sqlite` e depois:

```powershell
docker compose up -d postgres redis
python manage.py migrate
python manage.py runserver
```

## 2. O que já está incluído

- Usuários UUID identificados por e-mail e senhas com Argon2.
- Autenticação por sessão segura, proteção CSRF, limitação de requisições e bloqueio de login.
- Organizações e membros para SaaS multiempresa/multitenant.
- API REST versionada com paginação e documentação OpenAPI.
- Criptografia AES-256-GCM para campos confidenciais.
- Auditoria imutável, logs JSON e remoção de dados sensíveis dos logs.
- Finalidades de tratamento, avisos de privacidade, consentimentos e solicitações de titulares.
- PostgreSQL, Redis, Celery, Docker, CI e deploy no Fly.io.
- Sentry com ambiente, release, erros e traces; dados pessoais e credenciais são filtrados.

O projeto não inclui cadastro público, recuperação de senha, cobrança, MFA ou SSO. Esses fluxos
devem ser adicionados conforme as regras de cada produto.

## 3. Como consumir a API

A autenticação usa cookie de sessão e proteção CSRF. Em Python, instale `requests` e use uma
`Session` para preservar os cookies:

```powershell
python -m pip install requests
```

Exemplo completo de login e consulta:

```python
import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"
TIMEOUT = 10

session = requests.Session()
session.headers["Accept"] = "application/json"


def obter_csrf() -> str:
    response = session.get(f"{BASE_URL}/auth/csrf/", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["csrf_token"]


# O primeiro token autoriza o login.
csrf_token = obter_csrf()
login = session.post(
    f"{BASE_URL}/auth/login/",
    json={
        "email": "usuario@exemplo.com",
        "password": "senha-segura",
    },
    headers={"X-CSRFToken": csrf_token},
    timeout=TIMEOUT,
)
login.raise_for_status()

# O Django troca o token durante o login. Obtenha o novo token antes de alterar dados.
csrf_token = obter_csrf()

profile = session.get(f"{BASE_URL}/auth/me/", timeout=TIMEOUT)
profile.raise_for_status()
print(profile.json())
```

Para criar uma organização:

```python
organization = session.post(
    f"{BASE_URL}/organizations/",
    json={"name": "Empresa Exemplo", "slug": "empresa-exemplo"},
    headers={"X-CSRFToken": csrf_token},
    timeout=TIMEOUT,
)
organization.raise_for_status()
organization_id = organization.json()["id"]
```

Em APIs de negócio vinculadas a uma organização, inclua o tenant:

```python
tenant_headers = {
    "X-CSRFToken": csrf_token,
    "X-Organization-ID": organization_id,
}

# Troque "seu-recurso" pela rota criada para o seu produto.
response = session.get(
    f"{BASE_URL}/seu-recurso/",
    headers=tenant_headers,
    timeout=TIMEOUT,
)
response.raise_for_status()
```

Envie `X-CSRFToken` em qualquer `POST`, `PATCH`, `PUT` ou `DELETE`. Para encerrar:

```python
logout = session.post(
    f"{BASE_URL}/auth/logout/",
    headers={"X-CSRFToken": csrf_token},
    timeout=TIMEOUT,
)
logout.raise_for_status()
session.close()
```

Clientes Python não dependem de CORS. Use sempre HTTPS em produção, mantenha verificação TLS
ativa e nunca grave senha, cookie de sessão ou token em logs.

## 4. Endpoints disponíveis

| Método | Endpoint | Uso |
| --- | --- | --- |
| `GET` | `/api/v1/health/live/` | Processo está ativo |
| `GET` | `/api/v1/health/ready/` | PostgreSQL e Redis estão disponíveis |
| `GET` | `/api/v1/auth/csrf/` | Obter token CSRF |
| `POST` | `/api/v1/auth/login/` | Iniciar sessão |
| `POST` | `/api/v1/auth/logout/` | Encerrar sessão |
| `GET/PATCH` | `/api/v1/auth/me/` | Consultar ou alterar o perfil |
| `GET/POST` | `/api/v1/organizations/` | Listar ou criar organizações |
| `GET` | `/api/v1/organizations/{uuid}/` | Consultar uma organização |
| `GET` | `/api/v1/privacy/purposes/` | Listar finalidades ativas |
| `GET/POST` | `/api/v1/privacy/consents/` | Consultar ou registrar consentimento |
| `GET/POST` | `/api/v1/privacy/requests/` | Solicitações de titulares |

Antes de registrar consentimentos, cadastre no admin uma finalidade com base legal
`consent` e um aviso de privacidade ativo.

## 5. Usar organizações

Ao criar uma organização, o usuário atual recebe o papel `owner`. Nos endpoints de negócio que
tenham dados de uma organização, envie:

```text
X-Organization-ID: UUID_DA_ORGANIZACAO
```

O middleware valida se o usuário possui uma associação ativa. Novos modelos que armazenam
dados de clientes devem herdar de `OrganizationScopedModel`, e todas as consultas devem ser
filtradas por `request.organization`.

## 6. Criar uma nova API

Fluxo recomendado:

1. Crie um app dentro de `src/apps/`.
2. Crie o model; use `OrganizationScopedModel` se o dado pertencer a uma organização.
3. Crie serializer e view/viewset do Django REST Framework.
4. Defina permissões e filtre explicitamente pelo usuário ou organização.
5. Registre a rota em `src/config/urls_api.py`.
6. Crie migrations e testes de autorização e isolamento.

Comandos:

```powershell
python manage.py makemigrations
python manage.py migrate
pytest --cov
```

Para conectar APIs externas, guarde tokens somente em variáveis de ambiente/Fly Secrets,
configure timeout, trate retentativas e execute operações demoradas no Celery. Não envie dados
pessoais em URLs, argumentos de tarefas, logs ou eventos do Sentry.

## 7. Sentry

Crie um projeto Django no Sentry e configure o DSN:

```text
SENTRY_ENABLED=true
SENTRY_DSN=https://CHAVE@ORGANIZACAO.ingest.sentry.io/PROJETO
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.05
```

Em produção, o backend não inicia com Sentry habilitado e sem DSN. Corpos de requisição,
cookies, query strings, usuários, e-mails, tokens e variáveis locais são removidos antes do
envio. Também habilite a filtragem de dados no painel do Sentry.

## 8. Deploy resumido no Fly.io

```powershell
python scripts/configure_fly.py nome-unico-do-app
fly apps create nome-unico-do-app
python scripts/generate_production_secrets.py | fly secrets import -a nome-unico-do-app
fly mpg create
fly mpg attach ID_DO_POSTGRES -a nome-unico-do-app
fly redis create
fly storage create -a nome-unico-do-app
fly secrets set SENTRY_DSN="SEU_DSN" -a nome-unico-do-app
fly deploy
fly scale count web=2 worker=1 -a nome-unico-do-app
```

Após criar o Redis, configure sua URL privada em `REDIS_URL`, `CELERY_BROKER_URL` e
`CELERY_RESULT_BACKEND`. O deploy executa as migrations antes de publicar a nova versão.

```powershell
fly secrets set REDIS_URL="URL_PRIVADA" CELERY_BROKER_URL="URL_PRIVADA" CELERY_RESULT_BACKEND="URL_PRIVADA" -a nome-unico-do-app
```

Consulte o passo a passo completo em [deploy-fly.md](docs/pt-BR/deploy-fly.md).

## 9. Validar antes de publicar

```powershell
ruff check .
ruff format --check .
mypy src
pytest --cov
python manage.py check
python manage.py makemigrations --check --dry-run
```

Antes de receber dados reais, revise também [seguranca.md](docs/pt-BR/seguranca.md),
[lgpd.md](docs/pt-BR/lgpd.md), o
[runbook de incidentes](docs/pt-BR/runbooks/resposta-incidentes.md) e o
[runbook de backup](docs/pt-BR/runbooks/backup-restauracao.md).

As melhorias incorporadas após a revisão externa estão registradas em
[revisao-claude.md](docs/pt-BR/revisao-claude.md), incluindo trade-offs e migração de
ciphertexts antigos.

Se você está começando, leia [Tecnologias e middlewares: por que cada peça existe](docs/pt-BR/tecnologias-e-middlewares.md).
