import os
import sys

from django.apps import AppConfig


def should_start_serial_reader() -> bool:
    command = sys.argv[1] if len(sys.argv) > 1 else ""

    if command == "runserver":
        if "--noreload" in sys.argv:
            return True
        return os.environ.get("RUN_MAIN") == "true"

    if command in {"collectstatic", "makemigrations", "migrate", "shell", "test"}:
        return False

    return True


class ScaleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.scale"
    verbose_name = "Scale Integration"

    def ready(self):
        from django.conf import settings
        from . import serial_reader

        if not getattr(settings, "SCALE_ENABLED", True):
            serial_reader.set_scale_disabled()
            return

        if not should_start_serial_reader():
            return

        serial_reader.start_serial_reader(
            port=getattr(settings, "SERIAL_PORT", "AUTO"),
            baud_rate=getattr(settings, "SERIAL_BAUD_RATE", 9600),
        )
