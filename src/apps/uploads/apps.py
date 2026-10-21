from django.apps import AppConfig


class UploadsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.uploads"

    def ready(self) -> None:
        from apps.uploads import signals  # noqa: F401
