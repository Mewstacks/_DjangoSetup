"""Read-only questions about this codebase, answered from the code itself.

These functions need Django set up (they read the action registry, the data catalog and the app
registry) and never write anything. The development MCP server exposes them as tools, the test
suite calls them directly, and ``scripts/verify.py`` can too: one implementation, so an agent and
CI cannot disagree about what a convention means.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings

from devtools import conventions

ROOT = Path(__file__).resolve().parents[2]

# An organization column without OrganizationScopedModel, and why (see rule "tenant-model").
TENANT_MODEL_EXCEPTIONS = {
    "organizations.membership": "the link between people and organizations; read by membership",
    "audit.auditevent": "append-only trail; organization is a plain id so deletes never touch it",
    "actions.idempotencyrecord": "keyed by (organization, actor, key) inside the runtime",
    "flows.flowrun": "nullable on purpose (system flows); read through ctx.scoped_nullable",
    "flags.flagrule": "nullable: a rule may be global; read through flags.services",
    "flags.setting": "nullable: a setting may be global; read through flags.services",
}

# A field whose name says it holds data about a person (rule "list-personal-fields").
PERSONAL_NAME = re.compile(
    r"(^|_)(e?mail|phone|cpf|cnpj|document|address|birth|ip|ip_address|user_agent|first_name|"
    r"last_name|full_name|username|latitude|longitude|passport|rg)($|_)",
    re.IGNORECASE,
)

# Looks personal, was reviewed, is not (or is covered another way). Needs a written reason.
REVIEWED_FIELDS: dict[str, dict[str, str]] = {
    "privacy.cookieconsent": {"evidence": "holds only salted hashes of the agent and the address"},
    "privacy.datasubject": {
        "email_index": "a keyed HMAC blind index; it cannot be reversed without the key",
    },
}

CATEGORY_GUESS = (
    (re.compile(r"e?mail|phone|address"), "CONTACT"),
    (re.compile(r"name|cpf|cnpj|document|passport|^rg$|username|birth"), "IDENTIFIER"),
    (re.compile(r"(^|_)ip|user_agent|device|session"), "TECHNICAL"),
    (re.compile(r"latitude|longitude|location|geo"), "LOCATION"),
    (re.compile(r"price|amount|balance|card|iban|account_number"), "FINANCIAL"),
)


@dataclass(frozen=True, slots=True)
class Finding:
    severity: str  # "error" fails the gate, "warning" is advice
    rule: str
    where: str
    message: str
    fix: str = ""


def _local_apps() -> list[str]:
    return [name.removeprefix("apps.") for name in settings.LOCAL_APPS if name.startswith("apps.")]


def describe_project() -> dict[str, Any]:
    from apps.actions.registry import REGISTRY

    per_app = {}
    for name in _local_apps():
        folder = ROOT / "src" / "apps" / name
        per_app[name] = sorted(
            file for file, *_ in conventions.CONVENTION_FILES if (folder / file).exists()
        )
    return {
        **conventions.PROJECT,
        "settings_module": settings.SETTINGS_MODULE,
        "apps": per_app,
        "actions": len(REGISTRY),
        "models": len(apps.get_models()),
        "switches": {
            name: bool(getattr(settings, name, False))
            for name in (
                "OAUTH_ENABLED",
                "MCP_ENABLED",
                "TEMPORAL_ENABLED",
                "SIGNUP_ENABLED",
                "OTEL_ENABLED",
                "ADMIN_ENABLED",
            )
        },
        "commands": [{"what": what, "run": cmd} for what, cmd in conventions.COMMANDS],
        "convention_files": [
            {"file": f, "becomes": becomes, "discovered_by": by}
            for f, becomes, by in conventions.CONVENTION_FILES
        ],
        "where_to_look": [{"topic": t, "path": p} for t, p in conventions.WHERE_TO_LOOK],
    }


def list_conventions() -> dict[str, Any]:
    return {
        "rules": [asdict(rule) for rule in conventions.RULES],
        "definition_of_done": list(conventions.DEFINITION_OF_DONE),
        "forbidden": list(conventions.FORBIDDEN),
        "lgpd_decisions": [{"question": q, "answer": a} for q, a in conventions.LGPD_DECISIONS],
    }


def list_actions() -> list[dict[str, Any]]:
    from apps.actions.registry import REGISTRY

    return [
        {
            "name": spec.name,
            "write": spec.write,
            "scope": spec.scope,
            "summary": spec.description.splitlines()[0],
        }
        for spec in sorted(REGISTRY.values(), key=lambda s: s.name)
    ]


def explain_action(name: str) -> dict[str, Any]:
    from apps.actions.mcp.tools import tool_name
    from apps.actions.registry import REGISTRY
    from apps.actions.rest import describe

    spec = REGISTRY.get(name)
    if spec is None:
        close = sorted(n for n in REGISTRY if name.split(".")[0] in n)[:8]
        return {"error": f"No action named {name!r}.", "did_you_mean": close}
    try:
        source = inspect.getsourcefile(spec.fn)
        line = inspect.getsourcelines(spec.fn)[1]
        location = f"{Path(source).resolve().relative_to(ROOT).as_posix()}:{line}" if source else ""
    except (OSError, TypeError, ValueError):
        location = ""
    return {
        **describe(spec),
        "defined_at": location,
        "mcp_tool": tool_name(spec.name) if "mcp" in spec.channels else None,
        "rest": f"POST /api/v1/actions/{spec.name}/" if "api" in spec.channels else None,
        "cli": f"python manage.py action run {spec.name} --as <email> --org <slug> --json '{{}}'"
        if "cli" in spec.channels
        else None,
    }


# --- checks ------------------------------------------------------------------------------------


def _scan_tenant_door() -> list[Finding]:
    paths = [
        *(ROOT / "src/apps").glob("*/actions.py"),
        *(ROOT / "src/apps").glob("*/actions/*.py"),
        *(ROOT / "src/apps").glob("*/agent.py"),
    ]
    found = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"objects", "_default_manager"}:
                found.append(
                    Finding(
                        "error",
                        "tenant-door",
                        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}",
                        "Model.objects in a module that runs as the caller.",
                        "Use ctx.scoped(Model) or ctx.get(Model, id).",
                    )
                )
    return found


def _scan_models() -> list[Finding]:
    from apps.organizations.models import Organization, OrganizationScopedModel
    from apps.privacy.catalog import unclassified

    found = [
        Finding(
            "error",
            "classify-every-model",
            label,
            "The model has no entry in the data catalog.",
            f"Add personal(...) or not_personal(..., 'why') to <app>/privacy.py (try the "
            f"lgpd_check tool for {label}).",
        )
        for label in unclassified()
    ]
    for model in apps.get_models():
        field = next((f for f in model._meta.get_fields() if f.name == "organization"), None)
        if field is None or getattr(field, "related_model", None) is not Organization:
            continue
        if not issubclass(model, OrganizationScopedModel) and (
            model._meta.label_lower not in TENANT_MODEL_EXCEPTIONS
        ):
            found.append(
                Finding(
                    "error",
                    "tenant-model",
                    model._meta.label,
                    "A model with an organization column is not OrganizationScopedModel.",
                    "Subclass OrganizationScopedModel, or explain it in TENANT_MODEL_EXCEPTIONS.",
                )
            )
    return found


def _scan_personal_fields() -> list[Finding]:
    from apps.common.encryption import EncryptedTextField
    from apps.privacy.catalog import CATALOG, SENSITIVE_CATEGORIES

    found = []
    for label, item in sorted(CATALOG.items()):
        if not item.personal:
            continue
        model = apps.get_model(label)
        reviewed = REVIEWED_FIELDS.get(label, {})
        for field in model._meta.get_fields():
            if (
                getattr(field, "concrete", False)
                and PERSONAL_NAME.search(field.name)
                and field.name not in item.fields
                and field.name not in reviewed
            ):
                found.append(
                    Finding(
                        "error",
                        "list-personal-fields",
                        f"{label}.{field.name}",
                        "Looks like personal data but is not in personal(fields=...).",
                        "List it with a Category (export and erasure skip unlisted fields).",
                    )
                )
        for name, category in item.fields.items():
            if category in SENSITIVE_CATEGORIES and not isinstance(
                model._meta.get_field(name), EncryptedTextField
            ):
                found.append(
                    Finding(
                        "error",
                        "list-personal-fields",
                        f"{label}.{name}",
                        "Sensitive or child data stored in clear text.",
                        "Use EncryptedTextField.",
                    )
                )
    return found


def _scan_generated_files() -> list[Finding]:
    from apps.actions.management.commands.actions_catalog import DEFAULT_PATH, render

    found = []
    target = ROOT / DEFAULT_PATH
    if not target.exists() or target.read_text(encoding="utf-8") != render():
        found.append(
            Finding(
                "error",
                "generated-files",
                "docs/reference/actions.json",
                "The action catalog is out of date.",
                "python manage.py actions_catalog",
            )
        )
    from devtools import context_files

    for name, content in context_files.render_all().items():
        path = ROOT / name
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            found.append(
                Finding(
                    "error",
                    "generated-files",
                    name,
                    "An AI context file is out of date.",
                    "python scripts/gen_docs.py",
                )
            )
    return found


FORBIDDEN_PATTERNS = (
    (re.compile(r"\beval\("), "eval() runs text as code"),
    (re.compile(r"\bpickle\.loads?\("), "pickle runs code on load"),
    (re.compile(r"yaml\.load\((?!.*Loader=yaml\.SafeLoader)"), "yaml.load without SafeLoader"),
    (re.compile(r"shell\s*=\s*True"), "subprocess with shell=True"),
    (re.compile(r"\.execute\(\s*f[\"']"), "SQL built with an f-string"),
    (re.compile(r"verify\s*=\s*False"), "TLS verification switched off"),
    (re.compile(r"except\s+Exception\s*:\s*\n\s*pass\b"), "an exception swallowed silently"),
)
OUTBOUND = re.compile(r"\b(requests|httpx|urllib3)\.(get|post|put|patch|delete|request|Client)\b")
OUTBOUND_ALLOWED = {
    "src/apps/common/netguard.py",  # the guard itself
    "src/apps/flows/runner.py",
}


def _scan_forbidden() -> list[Finding]:
    found = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if "/migrations/" in relative or relative.startswith("src/devtools/"):
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for pattern, why in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    found.append(
                        Finding("error", "forbidden", f"{relative}:{number}", why, "Do not.")
                    )
            if OUTBOUND.search(line) and relative not in OUTBOUND_ALLOWED:
                found.append(
                    Finding(
                        "warning",
                        "outbound-http",
                        f"{relative}:{number}",
                        "Direct outbound HTTP.",
                        "If the URL is user-supplied, go through apps.common.netguard.",
                    )
                )
    return found


def check_conventions(*, include_generated: bool = True) -> list[Finding]:
    found = [*_scan_tenant_door(), *_scan_models(), *_scan_personal_fields(), *_scan_forbidden()]
    if include_generated:
        found += _scan_generated_files()
    return found


def as_dicts(findings: list[Finding]) -> list[dict[str, str]]:
    return [asdict(f) for f in findings]


# --- LGPD helper -----------------------------------------------------------------------------


def lgpd_check(label: str) -> dict[str, Any]:
    """The catalog entry for a model, or a proposed one with the decisions left to a person."""
    from apps.common.encryption import EncryptedTextField
    from apps.privacy.catalog import CATALOG

    try:
        model = apps.get_model(label)
    except (LookupError, ValueError):
        known = sorted(
            m._meta.label_lower
            for m in apps.get_models()
            if label.split(".")[-1] in m._meta.label_lower
        )
        return {"error": f"Unknown model {label!r}.", "did_you_mean": known[:8]}
    label = model._meta.label_lower
    entry = CATALOG.get(label)
    if entry is not None:
        return {
            "classified": True,
            "personal": entry.personal,
            "fields": {name: category.value for name, category in entry.fields.items()},
            "purpose": entry.purpose,
            "on_erase": entry.on_erase,
            "retention_field": entry.retention_field,
            "reason": entry.reason,
        }
    guesses: dict[str, str] = {}
    for field in model._meta.get_fields():
        if not getattr(field, "concrete", False) or field.primary_key or field.is_relation:
            continue
        if field.name in {"created_at", "updated_at", "archived_at"}:
            continue
        category = next(
            (c for pattern, c in CATEGORY_GUESS if pattern.search(field.name.lower())), ""
        )
        if not category and field.get_internal_type() in {"CharField", "TextField"}:
            category = "CONTENT"
        if category:
            guesses[field.name] = category
    plain_text = [
        name
        for name, category in guesses.items()
        if category in {"CONTENT", "CONTACT", "IDENTIFIER"}
        and not isinstance(model._meta.get_field(name), EncryptedTextField)
    ]
    body = ", ".join(f'"{n}": Category.{c}' for n, c in guesses.items())
    stub = (
        f"from {model.__module__.rsplit('.', 1)[0]}.models import {model.__name__}\n"
        "from apps.privacy.catalog import Category, by_user, personal\n\n"
        f"personal(\n    {model.__name__},\n    resolver=by_user({model.__name__}, 'created_by'),"
        f"\n    fields={{{body}}},\n    purpose='product-content',\n    retention_field='created_at',"
        "\n    on_erase='anonymize',\n    anonymize={...},  # a replacement value per field\n)\n"
        if guesses
        else f"not_personal({model.__name__}, 'why this holds no data about a person')\n"
    )
    return {
        "classified": False,
        "proposed_entry": stub,
        "guessed_categories": guesses,
        "stored_in_clear_text": plain_text,
        "decisions": [{"question": q, "answer": a} for q, a in conventions.LGPD_DECISIONS],
        "note": "A guess from field names. A person decides what is really personal data.",
    }


# --- docs ----------------------------------------------------------------------------------


def _doc_files(lang: str) -> list[Path]:
    base = ROOT / "docs" / lang
    return sorted(base.rglob("*.md")) if base.exists() else []


def search_docs(query: str, lang: str = "en", limit: int = 8) -> list[dict[str, Any]]:
    terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
    if not terms:
        return []
    scored = []
    for path in _doc_files(lang):
        text = path.read_text(encoding="utf-8")
        low = text.lower()
        score = sum(low.count(t) for t in terms) + 5 * sum(t in path.name.lower() for t in terms)
        if score:
            first = next(
                (i for i, line in enumerate(text.splitlines()) if terms[0] in line.lower()), 0
            )
            lines = text.splitlines()
            snippet = " ".join(lines[max(first - 1, 0) : first + 3])[:300]
            scored.append((score, path, snippet))
    scored.sort(key=lambda item: -item[0])
    return [
        {"path": p.relative_to(ROOT).as_posix(), "score": s, "snippet": snippet}
        for s, p, snippet in scored[:limit]
    ]


def get_doc(path: str) -> str:
    """One documentation page or AGENTS.md. Only files under docs/ (and the root guides)."""
    candidate = (ROOT / path).resolve()
    allowed = [ROOT / "docs", ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "README.en.md"]
    if not any(candidate == a.resolve() or a.resolve() in candidate.parents for a in allowed):
        raise ValueError("Only files under docs/ and the root guides can be read.")
    if candidate.suffix not in {".md", ".json"} or not candidate.is_file():
        raise ValueError(f"No such document: {path}")
    return candidate.read_text(encoding="utf-8")


def catalog_json(kind: str) -> str:
    if kind == "actions":
        from apps.actions.management.commands.actions_catalog import render

        return render()
    from apps.privacy.catalog import CATALOG

    return json.dumps(
        {
            label: {
                "personal": item.personal,
                "fields": {n: c.value for n, c in item.fields.items()},
                "purpose": item.purpose,
                "on_erase": item.on_erase,
                "retention_field": item.retention_field,
                "reason": item.reason,
            }
            for label, item in sorted(CATALOG.items())
        },
        indent=2,
        ensure_ascii=False,
    )


# --- Framework introspection ---------------------------------------------------------------

PRIMER = "docs/en/guides/framework-primer.md"


def middleware_stack() -> list[dict[str, Any]]:
    """The live middleware order, outermost first, with each class's own summary line."""
    from django.conf import settings
    from django.utils.module_loading import import_string

    stack = []
    for position, path in enumerate(settings.MIDDLEWARE, start=1):
        try:
            summary = (import_string(path).__doc__ or "").strip().splitlines()
        except ImportError:
            summary = ["(not importable)"]
        stack.append(
            {
                "order": position,
                "middleware": path,
                "summary": summary[0] if summary else "",
                "first_party": path.startswith("apps."),
            }
        )
    return stack


def list_routes() -> list[dict[str, str]]:
    """Every URL pattern: path, name and the view that serves it."""
    from django.urls import URLPattern, URLResolver, get_resolver

    routes: list[dict[str, str]] = []

    def walk(patterns: Any, prefix: str) -> None:
        for entry in patterns:
            if isinstance(entry, URLResolver):
                walk(entry.url_patterns, prefix + str(entry.pattern))
            elif isinstance(entry, URLPattern):
                callback = entry.callback
                view = getattr(callback, "view_class", callback)
                routes.append(
                    {
                        "path": "/" + (prefix + str(entry.pattern)).lstrip("/"),
                        "name": entry.name or "",
                        "view": f"{view.__module__}.{view.__qualname__}",
                    }
                )

    walk(get_resolver().url_patterns, "")
    return routes


def framework_topics() -> list[str]:
    text = (ROOT / PRIMER).read_text(encoding="utf-8")
    return [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]


def framework_guide(topic: str = "") -> str:
    """One section of the framework primer, matched by a word of its heading."""
    text = (ROOT / PRIMER).read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## ", text)[1:]
    wanted = topic.strip().lower()
    if wanted:
        for section in sections:
            title = section.splitlines()[0].lower()
            if wanted in title or any(word in title for word in wanted.split() if len(word) > 3):
                return "## " + section.strip()
    return "Topics: " + "; ".join(framework_topics())
