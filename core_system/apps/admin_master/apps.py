"""Django app configuration for admin-master startup hooks."""

from django.apps import AppConfig


class AdminMasterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.admin_master"
    label = "admin_master"

    def ready(self):
        from django.db.models.signals import post_migrate

        try:
            from . import signals  # noqa: F401
        except Exception:
            pass

        def run_dev_bootstrap(**kwargs):
            try:
                from .bootstrap import ensure_dev_master_data

                ensure_dev_master_data()
            except Exception:
                return

        post_migrate.connect(
            run_dev_bootstrap,
            sender=self,
            dispatch_uid="admin_master.run_dev_bootstrap",
            weak=False,
        )
