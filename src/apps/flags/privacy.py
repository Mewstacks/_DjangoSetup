from apps.flags.models import Flag, FlagRule, Setting
from apps.privacy.catalog import Category, by_user, not_personal, personal

not_personal(Flag, "A feature switch.")
not_personal(Setting, "A runtime configuration value for the product or an organization.")
personal(
    FlagRule,
    resolver=by_user(FlagRule, "user"),
    fields={"user": Category.IDENTIFIER},
    purpose="product-content",
    on_erase="delete",
)
