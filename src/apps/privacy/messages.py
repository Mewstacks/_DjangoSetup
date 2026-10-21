"""The words a data subject reads: e-mails and the summary stored on a request.

LGPD art. 9 asks for clear, adequate and *ostensive* information, which in a Brazilian product
means Portuguese first. The texts live here, in code, because they have to be testable and
reviewable like any rule (a gettext catalog adds a build step for ten sentences). Add a language
by adding a key to ``CATALOG``; ``PRIVACY_MAIL_LANGUAGE`` picks it, and a missing key falls back to
English rather than failing a request.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

CATALOG: dict[str, dict[str, str]] = {
    "en": {
        "confirm.subject": "Confirm your request",
        "confirm.body": "Confirm that you made this request: {token}\n",
        "export.subject": "Your data export is ready",
        "export.body": "Download within {days} days (the link works {uses} times):\n{link}\n",
        "export.summary": "Your export is ready; the download link was sent to you.",
        "confirmation.summary": "We process your data for: {purposes}. {holds}",
        "confirmation.holds_yes": "We hold data about you ({kinds} kinds of record).",
        "confirmation.holds_no": "We hold no personal data about you.",
        "deletion.summary": "Done. {count} kinds of record were reviewed; see your request "
        "history.",
        "blocking.summary": "Processing is blocked and your account was deactivated.",
        "withdrawal.summary": "{count} consent(s) withdrawn.",
        "sharing.summary": "We share data with: {vendors}.",
        "sharing.none": "no third parties",
        "denied.subject": "About your request",
        "completed.subject": "Your request was completed",
        "answered.subject": "Your request was answered",
        "answered.default": "Your request was handled.",
        "export.readme": (
            "Your data, as we hold it.\n\n"
            "data.json holds one list per kind of record (the key is the table). Passwords and "
            "other credentials are never included. This file was generated at {at} for request "
            "{request}.\n"
        ),
    },
    "pt-br": {
        "confirm.subject": "Confirme sua solicitação",
        "confirm.body": "Confirme que você fez esta solicitação: {token}\n",
        "export.subject": "Sua exportação de dados está pronta",
        "export.body": "Baixe em até {days} dias (o link funciona {uses} vezes):\n{link}\n",
        "export.summary": "Sua exportação está pronta; o link para baixar foi enviado a você.",
        "confirmation.summary": "Tratamos seus dados para: {purposes}. {holds}",
        "confirmation.holds_yes": "Temos dados pessoais seus ({kinds} tipos de registro).",
        "confirmation.holds_no": "Não temos dados pessoais seus.",
        "deletion.summary": "Concluído. {count} tipos de registro foram analisados; veja o "
        "histórico da solicitação.",
        "blocking.summary": "O tratamento foi bloqueado e sua conta foi desativada.",
        "withdrawal.summary": "{count} consentimento(s) revogado(s).",
        "sharing.summary": "Compartilhamos dados com: {vendors}.",
        "sharing.none": "nenhum terceiro",
        "denied.subject": "Sobre sua solicitação",
        "completed.subject": "Sua solicitação foi concluída",
        "answered.subject": "Sua solicitação foi respondida",
        "answered.default": "Sua solicitação foi atendida.",
        "export.readme": (
            "Seus dados, como os mantemos.\n\n"
            "data.json traz uma lista por tipo de registro (a chave é a tabela). Senhas e outras "
            "credenciais nunca são incluídas. Este arquivo foi gerado em {at} para a "
            "solicitação {request}.\n"
        ),
    },
}


def language() -> str:
    chosen = str(getattr(settings, "PRIVACY_MAIL_LANGUAGE", "en")).lower()
    return chosen if chosen in CATALOG else "en"


def say(key: str, **values: Any) -> str:
    """The text for ``key`` in the configured language, with ``values`` filled in."""
    text = CATALOG[language()].get(key) or CATALOG["en"][key]
    return text.format(**values) if values else text
