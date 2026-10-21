"""Age assurance: a hook, because the right answer depends on the product.

LGPD art. 14 requires a parent's or guardian's specific consent for a child's data, and the
ECA Digital (Lei 15.211/2025, in force since 17 March 2026) asks products likely to be used by
minors for age *assurance* that is reliable, auditable and proportionate: a checkbox saying
"I am over 18" does not qualify. How to assure age (a document check, a verified credential, a
trusted third party, an estimate) is a product and legal decision with privacy costs of its own,
so the platform ships the seam rather than a method:

* ``AGE_ASSURANCE_BACKEND`` names a class with ``assess(user) -> AgeAssurance``;
* the consent API refuses a grant from somebody the backend reports as a minor unless a
  guardian confirmed it;
* the default backend, ``NoAssurance``, reports "cannot tell", which changes nothing.

Keep only what the decision needs (``is_minor`` and how it was reached), never the document.
The ANPD's guidance on age assurance is still developing: confirm the method with counsel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True, slots=True)
class AgeAssurance:
    is_minor: bool | None  # None: the backend could not tell
    method: str = "none"  # "document", "credential", "third_party", "estimate", ...
    verified: bool = False  # reached by a method that is reliable and auditable


class AgeAssuranceBackend(Protocol):
    def assess(self, user: Any) -> AgeAssurance: ...


class NoAssurance:
    """Says it cannot tell. A deployment aimed at minors must replace it."""

    def assess(self, user: Any) -> AgeAssurance:
        return AgeAssurance(is_minor=None)


def assess(user: Any) -> AgeAssurance:
    backend: AgeAssuranceBackend = import_string(settings.AGE_ASSURANCE_BACKEND)()
    return backend.assess(user)
