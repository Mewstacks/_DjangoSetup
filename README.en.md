# Quick usage guide

[Versão em português](README.md) · [Documentation index](docs/README.md)

This project is a reusable Django SaaS backend. It includes authentication, a REST API,
organizations, technical LGPD controls, encryption, audit trails, background tasks, Sentry,
and Fly.io deployment configuration.

> The technical controls help with security and accountability evidence, but do not make a
> product automatically compliant. Each SaaS still needs product-specific purposes, lawful
> bases, retention, vendors, privacy notices, and accountable owners.

## 1. Run locally

Python 3.12 is required. For a quick SQLite setup:

```powershell
python -m pip install uv==0.12.0
uv sync --locked --all-extras
.\.venv\Scripts\Activate.ps1
python scripts/init_local.py --sqlite
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Local addresses:

- API: `http://127.0.0.1:8000/api/v1/`
- Swagger: `http://127.0.0.1:8000/api/docs/`
- Admin: `http://127.0.0.1:8000/admin/`

Swagger and Django Admin are disabled by default in production.

For local PostgreSQL and Redis, install Docker, run `python scripts/init_local.py` without
`--sqlite`, then:

```powershell
docker compose up -d postgres redis
python manage.py migrate
python manage.py runserver
```

## 2. Included features

- UUID users identified by email and Argon2 password hashing.
- Secure session authentication, CSRF, request throttling, and login lockouts.
- Organizations and memberships for multi-company/multitenant SaaS products.
- Versioned REST API with pagination and OpenAPI documentation.
- AES-256-GCM encryption for confidential fields.
- Immutable audit records, JSON logs, and sensitive-data redaction.
- Processing purposes, privacy notices, consent evidence, and data-subject requests.
- PostgreSQL, Redis, Celery, Docker, CI, and Fly.io deployment.
- Sentry error and trace capture with personal data and credentials filtered.

The starter does not include public signup, password recovery, billing, MFA, or SSO. Add those
flows according to each product's requirements.

## 3. Consume the API with Python

Authentication uses a session cookie and CSRF protection. Install `requests` and keep cookies
in a `Session`:

```powershell
python -m pip install requests
```

Complete login and profile example:

```python
import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"
TIMEOUT = 10

session = requests.Session()
session.headers["Accept"] = "application/json"


def get_csrf() -> str:
    response = session.get(f"{BASE_URL}/auth/csrf/", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["csrf_token"]


# The first token authorizes login.
csrf_token = get_csrf()
login = session.post(
    f"{BASE_URL}/auth/login/",
    json={
        "email": "user@example.com",
        "password": "secure-password",
    },
    headers={"X-CSRFToken": csrf_token},
    timeout=TIMEOUT,
)
login.raise_for_status()

# Django rotates the token during login. Fetch it again before changing data.
csrf_token = get_csrf()

profile = session.get(f"{BASE_URL}/auth/me/", timeout=TIMEOUT)
profile.raise_for_status()
print(profile.json())
```

Create an organization:

```python
organization = session.post(
    f"{BASE_URL}/organizations/",
    json={"name": "Example Company", "slug": "example-company"},
    headers={"X-CSRFToken": csrf_token},
    timeout=TIMEOUT,
)
organization.raise_for_status()
organization_id = organization.json()["id"]
```

For organization-owned product APIs, include the tenant:

```python
tenant_headers = {
    "X-CSRFToken": csrf_token,
    "X-Organization-ID": organization_id,
}

# Replace "your-resource" with a route created for your product.
response = session.get(
    f"{BASE_URL}/your-resource/",
    headers=tenant_headers,
    timeout=TIMEOUT,
)
response.raise_for_status()
```

Send `X-CSRFToken` with every `POST`, `PATCH`, `PUT`, or `DELETE`. To log out:

```python
logout = session.post(
    f"{BASE_URL}/auth/logout/",
    headers={"X-CSRFToken": csrf_token},
    timeout=TIMEOUT,
)
logout.raise_for_status()
session.close()
```

Python clients do not depend on CORS. Always use HTTPS in production, keep TLS verification
enabled, and never write passwords, session cookies, or tokens to logs.

## 4. Available endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health/live/` | Process liveness |
| `GET` | `/api/v1/health/ready/` | PostgreSQL and Redis readiness |
| `GET` | `/api/v1/auth/csrf/` | Get a CSRF token |
| `POST` | `/api/v1/auth/login/` | Start a session |
| `POST` | `/api/v1/auth/logout/` | End a session |
| `GET/PATCH` | `/api/v1/auth/me/` | Read or update the profile |
| `GET/POST` | `/api/v1/organizations/` | List or create organizations |
| `GET` | `/api/v1/organizations/{uuid}/` | Retrieve an organization |
| `GET` | `/api/v1/privacy/purposes/` | List active processing purposes |
| `GET/POST` | `/api/v1/privacy/consents/` | Read or record consent |
| `GET/POST` | `/api/v1/privacy/requests/` | Data-subject requests |

Before recording consent, create a processing purpose with the `consent` lawful basis and an
active privacy notice through Django Admin.

## 5. Use organizations

Creating an organization assigns the current user the `owner` role. For business endpoints
containing organization data, send:

```text
X-Organization-ID: ORGANIZATION_UUID
```

Middleware verifies the active membership. New customer-data models should inherit
`OrganizationScopedModel`, and all queries must be filtered by `request.organization`.

## 6. Create a new API

1. Create an app under `src/apps/`.
2. Create the model; use `OrganizationScopedModel` for organization-owned data.
3. Create its Django REST Framework serializer and view/viewset.
4. Define permissions and explicitly scope by user or organization.
5. Register the route in `src/config/urls_api.py`.
6. Create migrations and authorization/isolation tests.

```powershell
python manage.py makemigrations
python manage.py migrate
pytest --cov
```

For external APIs, keep tokens in environment variables/Fly Secrets, configure timeouts,
handle bounded retries, and run slow operations in Celery. Never place personal data in URLs,
task arguments, logs, or Sentry events.

## 7. Sentry

Create a Django project in Sentry and configure:

```text
SENTRY_ENABLED=true
SENTRY_DSN=https://KEY@ORGANIZATION.ingest.sentry.io/PROJECT
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.05
```

Production does not start when Sentry is enabled without a DSN. Request bodies, cookies, query
strings, users, emails, tokens, and local variables are removed before transmission. Enable
server-side data scrubbing in Sentry as a second layer.

## 8. Fly.io deployment summary

```powershell
python scripts/configure_fly.py your-unique-app-name
fly apps create your-unique-app-name
python scripts/generate_production_secrets.py | fly secrets import -a your-unique-app-name
fly mpg create
fly mpg attach YOUR_POSTGRES_ID -a your-unique-app-name
fly redis create
fly storage create -a your-unique-app-name
fly secrets set SENTRY_DSN="YOUR_DSN" -a your-unique-app-name
fly deploy
fly scale count web=2 worker=1 -a your-unique-app-name
```

After creating Redis, configure its private URL:

```powershell
fly secrets set REDIS_URL="PRIVATE_URL" CELERY_BROKER_URL="PRIVATE_URL" CELERY_RESULT_BACKEND="PRIVATE_URL" -a your-unique-app-name
```

Deployments run migrations before releasing the new version. See the full
[Fly.io deployment guide](docs/en/deployment-fly.md).

## 9. Validate before release

```powershell
ruff check .
ruff format --check .
mypy src
pytest --cov
python manage.py check
python manage.py makemigrations --check --dry-run
```

Before processing real data, read the [security model](docs/en/security.md),
[LGPD guide](docs/en/lgpd.md), [incident runbook](docs/en/runbooks/incident-response.md), and
[backup runbook](docs/en/runbooks/backup-restore.md).

Improvements incorporated after the external review are recorded in
[claude-review.md](docs/en/claude-review.md), including trade-offs and legacy-ciphertext
migration requirements.

If you are new to backend development, read
[Technologies and middleware: why every piece exists](docs/en/technologies-and-middleware.md).
