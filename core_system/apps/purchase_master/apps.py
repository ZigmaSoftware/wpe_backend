"""Django app configuration for purchase-master startup hooks."""

from django.apps import AppConfig


class PurchaseMasterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.purchase_master"
    label = "purchase_master"

    def ready(self):
        try:
            from .bootstrap import ensure_dev_purchase_master_data
            ensure_dev_purchase_master_data()
        except Exception:
            return
