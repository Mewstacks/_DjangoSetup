"""What an engineer or an AI agent must know to build on this platform, as data.

One source feeds everything an agent reads: ``AGENTS.md`` (and the files that point at it for
Claude Code, Cursor and Copilot), ``llms.txt``, ``docs/reference/conventions.json`` and the
development MCP server. Edit the rules here, run ``python scripts/gen_docs.py``, and every copy
changes together; ``gen_docs.py --check`` fails CI when one of them was edited by hand.

A rule is only listed when something enforces it (a test, an import-time check, a validator) or
when it is a judgement a machine cannot make and a person must. ``enforced_by`` says which.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    rule: str
    why: str
    enforced_by: str


PROJECT = {
    "name": "saas-django-backend",
    "summary": (
        "A security-first, LGPD-aware Django 6.1 foundation for a multi-tenant SaaS. One function "
        "declared with @action is a REST endpoint, an MCP tool, a Temporal activity and a CLI "
        "command at once."
    ),
    "stack": "Python 3.12+, Django 6.1, DRF, django-allauth (MFA), FastMCP, Temporal (optional), "
    "PostgreSQL, Redis, pydantic v2, structlog",
}

COMMANDS = (
    ("Install", "uv sync --all-extras"),
    (
        "First run (env, database, LGPD purposes, admin, organization)",
        "python scripts/bootstrap.py",
    ),
    ("Run", "python manage.py runserver"),
    ("Quality gate, fast (lint, tests, drift checks)", "python scripts/verify.py --fast"),
    (
        "Quality gate, full (adds mypy strict and the production deploy check)",
        "python scripts/verify.py",
    ),
    ("Tests", "python -m pytest -q"),
    ("Regenerate the action catalog", "python manage.py actions_catalog"),
    ("Regenerate the OpenAPI file", "python scripts/check_openapi.py --write"),
    ("Regenerate reference docs and AI context files", "python scripts/gen_docs.py"),
    (
        "Scaffold a tenant resource",
        "python manage.py scaffold resource <app> <Model> --fields 'title:str,body:text'",
    ),
    ("Is this deployment sound?", "python manage.py doctor"),
    ("Seed LGPD purposes and the platform's sub-processor stubs", "python manage.py privacy_seed"),
    ("Verify the audit hash chains", "python manage.py audit_verify"),
    ("Development MCP server for agents (stdio)", "python -m devtools.mcp"),
)

# <app>/<file>.py modules the platform discovers by name, and what each one becomes.
CONVENTION_FILES = (
    ("models.py", "Django models. Tenant data subclasses OrganizationScopedModel.", "-"),
    ("services.py", "Business rules, one implementation shared by REST viewsets and actions.", "-"),
    (
        "actions.py",
        "@action functions: REST /api/v1/actions/<name>/, MCP tool, CLI, Temporal activity.",
        "apps.actions.registry.autodiscover",
    ),
    (
        "undo.py",
        "@undo_handler functions that take back what a write action changed.",
        "apps.actions.registry.autodiscover",
    ),
    (
        "agent.py",
        "MCP resources (@mcp_resource) and prompts (@mcp_prompt) for AI agents.",
        "apps.actions.mcp.registry.autodiscover",
    ),
    (
        "events.py",
        "register_event(...): webhook event types other systems can subscribe to.",
        "apps.webhooks.events",
    ),
    (
        "privacy.py",
        "personal(...) / not_personal(...): the data catalog entry for every model (LGPD).",
        "apps.privacy.catalog.autodiscover",
    ),
    (
        "dynamic.py",
        "declare_setting(key, type, default, description): typed settings an operator can override.",
        "apps.flags.registry",
    ),
    ("workflows.py", "Temporal workflows (no Django ORM inside).", "apps.flows.registry"),
    ("activities.py", "Temporal activities (sync functions).", "apps.flows.registry"),
    (
        "jobs.py",
        "@job: cron-style maintenance, run by Temporal Schedules or run_scheduler.",
        "apps.flows.registry",
    ),
    (
        "api.py",
        "Classic DRF viewsets, only when a plain CRUD resource is wanted besides actions.",
        "config.urls_api",
    ),
)

RULES = (
    Rule(
        "tenant-door",
        "Reach tenant rows only through ctx.scoped(Model) or ctx.get(Model, id). Never "
        "Model.objects (or _default_manager) in actions.py, actions/*.py or agent.py.",
        "A forgotten organization filter is a cross-tenant leak (IDOR).",
        "tests/test_tenancy_structure.py (AST scan) and tests/test_actions.py",
    ),
    Rule(
        "tenant-model",
        "A model that holds tenant data subclasses apps.organizations.models.OrganizationScopedModel.",
        "It carries the organization foreign key the scoped helpers filter on.",
        "tests/test_tenancy_structure.py (every organization column is scoped or explained)",
    ),
    Rule(
        "thin-adapters",
        "Put business rules in services.py. Actions and viewsets only translate input and output.",
        "REST, MCP, CLI and Temporal then cannot disagree about a rule.",
        "review",
    ),
    Rule(
        "write-decides-undo",
        "A write action declares undoable=True (and records the change with ctx.record_change plus "
        "a handler in undo.py) or undoable='<why it cannot be undone>'. It also calls "
        "ctx.set_target(row) so the audit event names the record.",
        "An agent that changes data must be able to take the change back, or say it cannot.",
        "import-time check in apps.actions.registry and tests/test_conformance.py",
    ),
    Rule(
        "domain-errors",
        "Refuse with a DomainError subclass (NotFound, Forbidden, Invalid, Conflict) and a message "
        "written for the caller. Let anything else propagate as a bug.",
        "Django ValidationError text and ORM errors must not reach clients (they are masked).",
        "apps.common.exceptions, mask_error_details in the MCP server",
    ),
    Rule(
        "classify-every-model",
        "Every model is declared in <app>/privacy.py: personal(model, resolver=..., fields={...}, "
        "purpose=..., on_erase=...) or not_personal(model, 'why').",
        "Export, erasure, retention and the RoPA are generated from the catalog (LGPD art. 18, 37).",
        "tests/test_lgpd.py, tests/test_catalog_lint.py",
    ),
    Rule(
        "list-personal-fields",
        "List every field that holds data about a person (e-mail, phone, document, address, name, "
        "ip, user agent) in personal(fields=...). Sensitive and child data are EncryptedTextField.",
        "An unlisted field is skipped by export and erasure.",
        "tests/test_catalog_lint.py",
    ),
    Rule(
        "encrypt-free-text",
        "Use EncryptedTextField for free text that can contain personal data, and blind_index() "
        "for equality lookups on it. Never filter on an encrypted column.",
        "A database dump or a replica must not expose what people wrote.",
        "review; apps.common.encryption",
    ),
    Rule(
        "no-secrets-in-output",
        "Never put credentials, tokens or personal data in logs, audit metadata, action outputs "
        "or error messages. Audit metadata keys are snake_case ids and counts.",
        "Logs, traces and the audit trail outlive the data (LGPD art. 46).",
        "redaction pipeline, apps.audit.models.validate_metadata, tests/test_conformance.py",
    ),
    Rule(
        "outbound-http",
        "Call a URL somebody else chose only through apps.common.netguard. Never requests/httpx "
        "directly with a user-supplied URL.",
        "SSRF: the server would otherwise reach the cloud metadata service or the private network.",
        "tests/test_netguard.py; review",
    ),
    Rule(
        "events-are-thin",
        "register_event(...) in events.py and emit(...) inside the same transaction, with ids only "
        "in the payload.",
        "The outbox delivers after commit; receivers fetch documents through the API.",
        "apps.webhooks",
    ),
    Rule(
        "flows-no-orm",
        "Workflow code holds no Django ORM and no I/O; it calls actions through "
        "apps.flows.sdk.call_action. Activities are sync functions.",
        "Workflows are replayed deterministically.",
        "review; tests/test_flows.py",
    ),
    Rule(
        "settings-through-env",
        "Add configuration with env_str/env_int/env_bool/env_list in config/settings/*.py, with a "
        "comment above it. Production-only constraints go in config/settings/validators.py.",
        "The environment-variable reference is generated from these calls.",
        "scripts/gen_docs.py --check",
    ),
    Rule(
        "quotas",
        "A resource a tenant can create without bound checks apps.organizations.quotas.",
        "One tenant must not be able to fill the database or the bucket for all.",
        "review; tests/test_tenancy_structure.py",
    ),
    Rule(
        "csp-clean",
        "No inline scripts or styles and no third-party origins on shipped pages (script-src and "
        "style-src are 'self').",
        "The Content-Security-Policy is the second line of defence against injected script.",
        "tests/test_web_hardening.py",
    ),
    Rule(
        "migrations",
        "Never edit a migration that has shipped. Add a new one; keep data migrations idempotent.",
        "Other databases already applied the old one.",
        "makemigrations --check in scripts/verify.py",
    ),
    Rule(
        "bilingual-docs",
        "Every page under docs/en has a twin under docs/pt-BR. Generated references come from "
        "scripts/gen_docs.py; do not edit them by hand.",
        "The platform is documented for Brazilian teams first.",
        "tests/test_docs.py, scripts/gen_docs.py --check",
    ),
    Rule(
        "do-not-weaken",
        "Do not loosen a production validator, widen CORS, set NETGUARD_ALLOW_PRIVATE or DEBUG "
        "outside local settings, or catch and swallow an exception to make a test pass.",
        "These are the controls the threat model relies on (docs/en/security/threat-model.md).",
        "config/settings/validators.py, tests/test_security_regressions.py",
    ),
)

DEFINITION_OF_DONE = (
    "python scripts/verify.py passes (use --fast while iterating, the full gate before you stop).",
    "New model: classified in <app>/privacy.py; tenant data subclasses OrganizationScopedModel.",
    "New action: docstring written for a model reader, a scope, write/destructive/undoable "
    "declared, input and output are pydantic models.",
    "Generated files are fresh: actions_catalog, check_openapi.py --write, gen_docs.py.",
    "A test covers the new behaviour, including a cross-tenant attempt and a read-only role.",
    "Docs updated in docs/en and docs/pt-BR; the CHANGELOG has a line for anything a user sees.",
    "No secret, personal data or production detail appears in code, tests, logs or messages.",
)

LGPD_DECISIONS = (
    (
        "Does a row relate to a person (directly or by a key that can be traced back)?",
        "Yes: personal(...). No: not_personal(model, 'why'), and be ready to defend the reason.",
    ),
    (
        "Which kind of data is each field?",
        "Category.IDENTIFIER, CONTACT, CREDENTIAL, FINANCIAL, LOCATION, BEHAVIOR, CONTENT, TECHNICAL, "
        "SENSITIVE (art. 5 II) or CHILD (art. 14). Sensitive and child fields must be encrypted.",
    ),
    (
        "How is a person's row found?",
        "resolver: by_user(Model, 'field'), by_subject(...), by_email_index(...); None only when rows "
        "cannot be tied to a person (the DPO then answers by hand).",
    ),
    (
        "Why is it processed, and on what legal basis?",
        "purpose= a ProcessingPurpose code. Reuse a baseline one (account-and-access, product-content, "
        "security-and-audit, compliance-records) or add one in apps/privacy/baseline.py. Consent as the "
        "basis means a ConsentRecord chain and a withdrawal path.",
    ),
    (
        "What happens on erasure?",
        "on_erase='delete', 'anonymize' (give the replacement values) or 'keep' (give the legal duty "
        "that requires it as reason=...).",
    ),
    (
        "How long is it kept?",
        "retention_field= the timestamp that starts the clock; the purpose's retention_days ends it.",
    ),
    (
        "Does it involve children?",
        "Mark the purpose involves_children and require guardian confirmation; see "
        "apps/privacy/age.py and docs/en/lgpd/overview.md (ECA Digital).",
    ),
    (
        "Does a new vendor see the data?",
        "Add a SubProcessor (country, transfer mechanism: LGPD art. 33, Res. CD/ANPD 19/2024).",
    ),
)

FORBIDDEN = (
    "Model.objects in actions.py or agent.py (use ctx.scoped / ctx.get).",
    "requests.post(user_supplied_url) or httpx.get(user_supplied_url) (use apps.common.netguard).",
    "except Exception: pass, or catching an error only to silence a failing test.",
    "Logging request bodies, tokens, e-mail addresses or documents.",
    "csrf_exempt without a written reason, raw SQL built with f-strings, eval, pickle.",
    "Editing generated files (docs/reference/*, openapi-schema.yml, AGENTS.md) by hand.",
    "Storing an API key, token or secret in clear (hash it, or encrypt it with the key ring).",
)

WHERE_TO_LOOK = (
    ("Architecture and the request path", "docs/en/architecture.md"),
    (
        "How Django, DRF, Temporal and the middleware work here",
        "docs/en/guides/framework-primer.md",
    ),
    (
        "Add an action / a flow / a webhook event",
        "docs/en/guides/add-an-action.md, add-a-flow.md, webhooks.md",
    ),
    ("LGPD: what is automatic, what is yours", "docs/en/lgpd/overview.md, compliance-matrix.md"),
    ("Security: threat model, hardening, review status", "docs/en/security/*.md"),
    ("Every environment variable", "docs/en/reference/env-vars.md (generated)"),
    ("Every action, scope and MCP tool", "docs/en/reference/actions.md (generated)"),
    ("Deploying", "docs/en/deploy/overview.md, runbooks.md"),
)
