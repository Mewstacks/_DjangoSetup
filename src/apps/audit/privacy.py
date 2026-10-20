from apps.audit.models import AuditAnchor, AuditEvent
from apps.privacy.catalog import not_personal

not_personal(
    AuditEvent,
    "Pseudonymous by construction: actor and organization are ids, IPs are HMACs, metadata is "
    "validated to hold no personal data. Erasing a person leaves ids that resolve to nothing.",
)
not_personal(AuditAnchor, "A chain position and a hash.")
