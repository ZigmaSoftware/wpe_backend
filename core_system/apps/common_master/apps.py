"""Django app configuration for common-master startup hooks."""

from django.apps import AppConfig


class CommonMasterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common_master"
    label = "common_master"

    def ready(self):
        from django.db.models.signals import post_migrate

        def run_dev_bootstrap(**kwargs):
            try:
                from .bootstrap import ensure_dev_common_master_data

                ensure_dev_common_master_data()
            except Exception:
                return

        post_migrate.connect(
            run_dev_bootstrap,
            sender=self,
            dispatch_uid="common_master.run_dev_bootstrap",
            weak=False,
        )
