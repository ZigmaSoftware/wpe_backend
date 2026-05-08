"""Django app configuration for common-master startup hooks."""

from django.apps import AppConfig


class CommonMasterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common_master"
    label = "common_master"

    def ready(self):
        try:
            from .bootstrap import ensure_dev_common_master_data
            ensure_dev_common_master_data()
        except Exception:
            return
