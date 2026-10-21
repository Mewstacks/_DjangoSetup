"""Purposes every deployment starts from. ``manage.py privacy_seed`` creates what is missing.

They are a starting point to review with your DPO, not legal advice: the lawful basis,
retention and description are *your* decisions about *your* processing.
"""

from __future__ import annotations

from typing import Any

BASELINE_PURPOSES: list[dict[str, Any]] = [
    {
        "code": "account-and-access",
        "name": "Account and access",
        "description": "Create and secure the account, authenticate the person and keep the "
        "sessions, keys and tokens they create.",
        "lawful_basis": "contract",
        "data_categories": ["identifier", "contact", "credential", "technical"],
        "retention_days": 1825,
    },
    {
        "code": "product-content",
        "name": "Content created in the product",
        "description": "Store, show and process what people create while using the service.",
        "lawful_basis": "contract",
        "data_categories": ["content", "behavior"],
        "retention_days": 1825,
    },
    {
        "code": "security-and-audit",
        "name": "Security and audit trail",
        "description": "Detect abuse, investigate incidents and keep the records needed to "
        "show who did what (including access-application logs).",
        "lawful_basis": "legal_obligation",
        "data_categories": ["technical", "identifier"],
        # Matches AUDIT_RETENTION_DAYS (the prune job). Marco Civil art. 15 asks for six months
        # of access-application logs; a year leaves room to investigate. Decide with your DPO.
        "retention_days": 365,
    },
    {
        "code": "compliance-records",
        "name": "Proof of compliance",
        "description": "Keep consent records and the handling of data subject requests as "
        "evidence that the law was followed (LGPD art. 8 par. 2 and art. 16, I).",
        "lawful_basis": "legal_obligation",
        "data_categories": ["identifier", "contact"],
        "retention_days": 1825,
    },
]
BASELINE_CODES = {p["code"] for p in BASELINE_PURPOSES}
