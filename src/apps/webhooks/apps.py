from django.apps import AppConfig


class WebhooksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.webhooks"

    def ready(self) -> None:
        from apps.webhooks.events import autodiscover

        autodiscover()
