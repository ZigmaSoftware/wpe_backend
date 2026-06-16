from django.apps import AppConfig


class ScaleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.scale"
    verbose_name = "Scale Integration"

    def ready(self):
        from django.conf import settings
        from . import serial_reader

        if not getattr(settings, "SCALE_ENABLED", True):
            serial_reader.set_scale_disabled()
