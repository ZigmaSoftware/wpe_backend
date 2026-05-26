import os

from django.apps import AppConfig


class ScaleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.scale"
    verbose_name = "Scale Integration"

    def ready(self):
        # Start reader only in the real server process, not the autoreloader watcher
        run_main = os.environ.get("RUN_MAIN")
        if run_main not in ("true", None):
            return

        from django.conf import settings
        from . import serial_reader

        serial_reader.start_serial_reader(
            port=getattr(settings, "SERIAL_PORT", "AUTO"),
            baud_rate=getattr(settings, "SERIAL_BAUD_RATE", 9600),
        )
