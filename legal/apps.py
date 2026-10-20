from django.apps import AppConfig


class LegalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "legal"
    verbose_name = "Legal pages"

    def ready(self):
        from . import signals  # noqa: F401
