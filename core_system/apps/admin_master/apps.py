"""Django app configuration for admin-master startup hooks."""

from django.apps import AppConfig


class AdminMasterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.admin_master"
    label = "admin_master"

    def ready(self):
        try:
            from . import signals  # noqa: F401
            from .bootstrap import ensure_dev_master_data

            ensure_dev_master_data()
        except Exception:
            return
