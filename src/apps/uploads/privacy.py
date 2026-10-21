from apps.privacy.catalog import Category, by_user, personal
from apps.uploads.models import UploadedFile

personal(
    UploadedFile,
    resolver=by_user(UploadedFile, "uploaded_by"),
    fields={
        "file": Category.CONTENT,
        "original_name": Category.CONTENT,
        "uploaded_by": Category.IDENTIFIER,
    },
    purpose="product-content",
    retention_field="created_at",
    on_erase="delete",
)
