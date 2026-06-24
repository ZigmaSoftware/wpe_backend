import logging
import os
import platform
import sys

from django.apps import AppConfig


logger = logging.getLogger(__name__)


class ScaleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.scale"
    verbose_name = "Scale Integration"

    def ready(self):
        from django.conf import settings
        from . import serial_reader

        logger.warning(
            "[Scale startup] os=%s platform=%s scale_enabled=%s serial_port=%s baud_rate=%s "
            "bridge_device=%s workstation=%s server_url=%s port_diagnostics=%s",
            platform.platform(),
            sys.platform,
            getattr(settings, "SCALE_ENABLED", True),
            getattr(settings, "SERIAL_PORT", "AUTO"),
            getattr(settings, "SERIAL_BAUD_RATE", 9600),
            os.getenv("DEVICE_ID", ""),
            os.getenv("WORKSTATION_ID", ""),
            os.getenv("WPE_SERVER_URL", ""),
            serial_reader.format_port_diagnostics(),
        )

        if not getattr(settings, "SCALE_ENABLED", True):
            serial_reader.set_scale_disabled()
