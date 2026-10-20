"""Classification of the models that come with Django and third-party apps."""

from __future__ import annotations

import contextlib
from typing import Any

from django.apps import apps

from apps.privacy.catalog import Category, by_user, not_personal, personal


def _model(label: str) -> Any:
    return apps.get_model(label)


def register_third_party() -> None:
    not_personal(_model("auth.group"), "Role definitions, not people.")
    not_personal(_model("auth.permission"), "Permission definitions, not people.")
    not_personal(_model("contenttypes.contenttype"), "Model registry.")

    session = _model("sessions.session")
    not_personal(
        session,
        "Opaque signed session data; expires on its own and is deleted with the account's "
        "sessions when the subject is erased (see apps.privacy.services).",
    )

    log_entry = _model("admin.logentry")
    personal(
        log_entry,
        resolver=by_user(log_entry, "user"),
        fields={"object_repr": Category.CONTENT, "change_message": Category.CONTENT},
        purpose="security-and-audit",
        retention_field="action_time",
        on_erase="delete",
    )

    for label in ("axes.accessattempt", "axes.accesslog", "axes.accessfailurelog"):
        model = _model(label)
        personal(
            model,
            resolver=None,  # keyed by username/IP text, not by an account reference
            fields={"username": Category.IDENTIFIER, "ip_address": Category.TECHNICAL},
            purpose="security-and-audit",
            retention_field="attempt_time" if label.endswith("attempt") else "",
            on_erase="delete",
            reason="Brute-force protection records; pruned by axes' own reset and retention.",
        )
    not_personal(_model("axes.accessattemptexpiration"), "Expiry timestamps only.")

    for label in (
        "oauth2_provider.accesstoken",
        "oauth2_provider.refreshtoken",
        "oauth2_provider.grant",
        "oauth2_provider.idtoken",
        "oauth2_provider.devicegrant",
    ):
        try:
            model = _model(label)
        except LookupError:
            continue
        personal(
            model,
            resolver=by_user(model, "user"),
            fields={
                "user": Category.IDENTIFIER,
                **({"scope": Category.TECHNICAL} if hasattr(model, "scope") else {}),
            },
            purpose="account-and-access",
            on_erase="delete",
        )
    with contextlib.suppress(LookupError):
        not_personal(
            _model("oauth2_provider.application"),
            "A registered client (software), not a person; the platform never sets its owner.",
        )

    _register_accounts()


def _register_accounts() -> None:
    """django-allauth: addresses, confirmations, MFA authenticators, device sessions."""
    email = _model("account.emailaddress")
    personal(
        email,
        resolver=by_user(email, "user"),
        fields={"email": Category.CONTACT, "user": Category.IDENTIFIER},
        purpose="account-and-access",
        on_erase="delete",
    )
    confirmation = _model("account.emailconfirmation")

    def confirmations(subject: object) -> object:
        user_id = getattr(subject, "user_id", None)
        if user_id is None:
            return confirmation._default_manager.none()
        return confirmation._default_manager.filter(email_address__user_id=user_id)

    personal(
        confirmation,
        resolver=confirmations,  # type: ignore[arg-type]
        fields={"key": Category.CREDENTIAL},
        purpose="account-and-access",
        retention_field="created",
        on_erase="delete",
    )
    authenticator = _model("mfa.authenticator")
    personal(
        authenticator,
        resolver=by_user(authenticator, "user"),
        fields={"data": Category.CREDENTIAL, "user": Category.IDENTIFIER},
        purpose="account-and-access",
        on_erase="delete",
    )
    device = _model("usersessions.usersession")
    personal(
        device,
        resolver=by_user(device, "user"),
        fields={"ip": Category.TECHNICAL, "user_agent": Category.TECHNICAL},
        purpose="security-and-audit",
        on_erase="delete",
    )


register_third_party()
