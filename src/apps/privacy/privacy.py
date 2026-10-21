from apps.privacy.catalog import Category, by_subject, not_personal, personal, self_subject
from apps.privacy.models import (
    ConsentRecord,
    CookieConsent,
    DataSubject,
    DataSubjectRequest,
    ImpactAssessment,
    LegalHold,
    PersonalDataIncident,
    PrivacyNotice,
    PrivacyReminder,
    ProcessingPurpose,
    SubProcessor,
)

for model, reason in (
    (ProcessingPurpose, "Configuration: why we process, not about a person."),
    (PrivacyNotice, "The published notice text reference."),
    (SubProcessor, "Vendors, not people."),
    (ImpactAssessment, "An assessment of a processing operation; it names no data subject."),
    (PrivacyReminder, "Bookkeeping of reminders sent."),
):
    not_personal(model, reason)

personal(
    CookieConsent,
    resolver=None,  # keyed by a random visitor id the DPO cannot tie to a person without them
    fields={"visitor_id": Category.IDENTIFIER, "categories": Category.BEHAVIOR},
    purpose="compliance-records",
    retention_field="created_at",
    on_erase="delete",
)
personal(
    DataSubject,
    resolver=self_subject(DataSubject),
    fields={"email": Category.CONTACT},
    purpose="compliance-records",
    on_erase="anonymize",
    anonymize={"email": ""},
)
personal(
    ConsentRecord,
    resolver=by_subject(ConsentRecord, "user__data_subject"),
    fields={"evidence": Category.TECHNICAL},
    purpose="compliance-records",
    on_erase="keep",
    reason="Proof that consent was given or withdrawn (LGPD art. 8 par. 2, art. 16 I). It holds "
    "ids and hashes, no direct identifiers once the account row is anonymized.",
)
personal(
    DataSubjectRequest,
    resolver=by_subject(DataSubjectRequest),
    fields={"details": Category.CONTENT, "response_summary": Category.CONTENT},
    purpose="compliance-records",
    on_erase="keep",
    reason="Demonstrates that rights requests were answered (accountability, art. 6 X). The "
    "free-text fields are cleared when the subject is erased.",
)
personal(
    LegalHold,
    resolver=by_subject(LegalHold),
    fields={"reason": Category.CONTENT},
    purpose="compliance-records",
    on_erase="keep",
    reason="A legal duty to retain is the very reason the hold exists (art. 16 I).",
)
personal(
    PersonalDataIncident,
    resolver=None,
    fields={
        "summary": Category.CONTENT,
        "risk_assessment": Category.CONTENT,
        "measures_taken": Category.CONTENT,
    },
    purpose="compliance-records",
    on_erase="keep",
    reason="Incident records are kept at least five years (Resolution CD/ANPD 15/2024). They "
    "are not indexed per person; the DPO answers questions about them by hand.",
)
