from apps.apikeys.models import ApiKey
from apps.privacy.catalog import Category, by_user, personal

personal(
    ApiKey,
    resolver=by_user(ApiKey, "user"),
    fields={"label": Category.CONTENT, "allowed_ips": Category.TECHNICAL},
    purpose="account-and-access",
    on_erase="delete",
)
