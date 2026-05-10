from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"

    def ready(self):
        # Wire the worked-example version ledger pre_save handler.
        from . import signals  # noqa: F401
