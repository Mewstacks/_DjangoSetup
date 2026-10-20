from apps.accounts.models import User
from apps.privacy.catalog import Category, personal, self_user

personal(
    User,
    resolver=self_user(User),
    fields={
        "email": Category.CONTACT,
        "full_name": Category.IDENTIFIER,
        "password": Category.CREDENTIAL,
        "last_login": Category.BEHAVIOR,
    },
    purpose="account-and-access",
    # The row stays (foreign keys, audit trail); apps.privacy.services.anonymize_user rewrites it.
    on_erase="anonymize",
    anonymize={"full_name": ""},
)
