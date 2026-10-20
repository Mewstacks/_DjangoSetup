from apps.examples.models import Note
from apps.privacy.catalog import Category, by_user, personal

personal(
    Note,
    resolver=by_user(Note, "created_by"),
    fields={"title": Category.CONTENT, "body": Category.CONTENT},
    purpose="product-content",
    retention_field="created_at",
    on_erase="anonymize",
    anonymize={"title": "[removed]", "body": ""},
)
