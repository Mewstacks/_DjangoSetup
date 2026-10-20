from apps.organizations.models import Membership, Organization
from apps.privacy.catalog import Category, by_user, not_personal, personal

not_personal(
    Organization,
    "A tenant record (name, slug). Where the tenant is a person, the name is account data "
    "already covered by that person's User row and erased with the organization.",
)
personal(
    Membership,
    resolver=by_user(Membership, "user"),
    fields={"role": Category.TECHNICAL},
    purpose="account-and-access",
    on_erase="anonymize",
    anonymize={"is_active": False},
)
