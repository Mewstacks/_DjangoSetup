from django.apps import AppConfig


class FlagsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.flags"

    def ready(self) -> None:
        from apps.flags import signals  # noqa: F401  (cache invalidation)
        from apps.flags.registry import autodiscover

        autodiscover()
