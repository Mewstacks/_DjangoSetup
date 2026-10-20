"""The data catalog: what personal data lives where, why, for how long, and what happens to it.

LGPD asks a controller to know its own processing (art. 37 - the *registro das operações* -
and art. 6 - purpose, necessity, transparency). The catalog is that knowledge as code, next to
the models it describes, and it drives behaviour instead of being a document that rots:

* **export** (access and portability, art. 18 II and V) walks the catalog;
* **erasure** (art. 18 IV, VI) applies each model's ``on_erase`` rule;
* **retention** (art. 15, 16) deletes or anonymizes past ``purpose.retention_days``;
* **RoPA** (``manage.py privacy_ropa``) is generated from it.

Every model of every installed app must be classified here, either as personal data (with its
fields, purpose and erase rule) or explicitly as *not* personal with a reason. A test fails when
a new model is added without a decision, so "we forgot to think about it" cannot ship.

Put registrations in ``<app>/privacy.py``; they are discovered at startup.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from django.apps import apps
from django.db.models import Model, QuerySet


class Category(StrEnum):
    IDENTIFIER = "identifier"  # name, document numbers
    CONTACT = "contact"  # e-mail, phone, address
    CREDENTIAL = "credential"  # passwords, tokens, keys
    FINANCIAL = "financial"
    LOCATION = "location"
    BEHAVIOR = "behavior"  # activity, preferences
    CONTENT = "content"  # what the person wrote or uploaded
    TECHNICAL = "technical"  # ip, device, session
    SENSITIVE = "sensitive"  # art. 5 II: health, biometrics, beliefs...
    CHILD = "child"  # art. 14


SENSITIVE_CATEGORIES = frozenset({Category.SENSITIVE, Category.CHILD})
ERASE_RULES = ("delete", "anonymize", "keep")

Resolver = Callable[[Any], QuerySet[Any]]


@dataclass(frozen=True)
class Classification:
    model: type[Model]
    personal: bool
    reason: str = ""  # why not personal, or why kept
    resolver: Resolver | None = None  # DataSubject -> this model's rows about them
    fields: dict[str, Category] = field(default_factory=dict)
    purpose: str = ""
    retention_field: str = ""
    on_erase: str = "anonymize"
    anonymize: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.model._meta.label_lower

    @property
    def sensitive(self) -> bool:
        return bool(SENSITIVE_CATEGORIES & set(self.fields.values()))


CATALOG: dict[str, Classification] = {}


def not_personal(model: type[Model], reason: str) -> None:
    """Declare that ``model`` holds no personal data, and say why."""
    if not reason.strip():
        raise ValueError(f"{model.__name__}: say why it holds no personal data.")
    CATALOG[model._meta.label_lower] = Classification(model=model, personal=False, reason=reason)


def personal(
    model: type[Model],
    *,
    resolver: Resolver | None,
    fields: dict[str, Category],
    purpose: str,
    retention_field: str = "",
    on_erase: str = "anonymize",
    anonymize: dict[str, Any] | None = None,
    reason: str = "",
) -> None:
    """Declare ``model`` as personal data.

    ``resolver`` turns a ``DataSubject`` into this model's rows about them (``None`` means the
    rows cannot be found per person and are handled by the DPO). ``on_erase`` is ``delete``,
    ``anonymize`` (overwrite ``anonymize`` fields, keep the row) or ``keep`` (a legal duty or the
    proof of compliance requires it; ``reason`` is mandatory).
    """
    if on_erase not in ERASE_RULES:
        raise ValueError(f"on_erase must be one of {ERASE_RULES}")
    if on_erase == "keep" and not reason.strip():
        raise ValueError(f"{model.__name__}: keeping personal data needs a stated reason.")
    if on_erase == "anonymize" and not anonymize:
        raise ValueError(f"{model.__name__}: anonymize needs the replacement values.")
    CATALOG[model._meta.label_lower] = Classification(
        model=model,
        personal=True,
        reason=reason,
        resolver=resolver,
        fields=fields,
        purpose=purpose,
        retention_field=retention_field,
        on_erase=on_erase,
        anonymize=anonymize or {},
    )


def by_user(model: type[Model], field_name: str) -> Resolver:
    """Rows of ``model`` whose ``field_name`` points at the subject's account."""

    def resolve(subject: Any) -> QuerySet[Any]:
        if subject.user_id is None:
            return model._default_manager.none()
        return model._default_manager.filter(**{field_name: subject.user_id})

    return resolve


def self_user(model: type[Model]) -> Resolver:
    """For the user model itself: the subject's own account row."""

    def resolve(subject: Any) -> QuerySet[Any]:
        if subject.user_id is None:
            return model._default_manager.none()
        return model._default_manager.filter(pk=subject.user_id)

    return resolve


def self_subject(model: type[Model]) -> Resolver:
    """For the ``DataSubject`` model itself: the subject's own record."""

    def resolve(subject: Any) -> QuerySet[Any]:
        return model._default_manager.filter(pk=subject.pk)

    return resolve


def by_email_index(model: type[Model], field_name: str) -> Resolver:
    """Rows keyed by the subject's e-mail blind index (people without an account)."""

    def resolve(subject: Any) -> QuerySet[Any]:
        return model._default_manager.filter(**{field_name: subject.email_index})

    return resolve


def by_subject(model: type[Model], field_name: str = "subject") -> Resolver:
    """Rows that point straight at the ``DataSubject`` record."""

    def resolve(subject: Any) -> QuerySet[Any]:
        return model._default_manager.filter(**{field_name: subject})

    return resolve


def classification(model: type[Model]) -> Classification | None:
    return CATALOG.get(model._meta.label_lower)


def unclassified() -> list[str]:
    """Labels of installed models that nobody has made a decision about."""
    return sorted(
        m._meta.label_lower for m in apps.get_models() if m._meta.label_lower not in CATALOG
    )


def autodiscover() -> None:
    for config in apps.get_app_configs():
        module = f"{config.name}.privacy"
        try:
            importlib.import_module(module)
        except ModuleNotFoundError as exc:
            if exc.name != module:
                raise
    importlib.import_module("apps.privacy.third_party")
