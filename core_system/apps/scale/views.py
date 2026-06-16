import sys

from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from django.conf import settings

from .serial_reader import (
    get_disabled_weight, get_latest_weight, list_available_ports,
    find_auto_port, start_serial_reader, stop_serial_reader,
    _reader_thread,
)


class LatestWeightView(View):
    """GET /api/scale/weight/latest/ — returns most recent reading from serial port."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        if not getattr(settings, "SCALE_ENABLED", True):
            return JsonResponse(get_disabled_weight())

        port = getattr(settings, "SERIAL_PORT", "AUTO")
        baud = getattr(settings, "SERIAL_BAUD_RATE", 9600)

        if port == "AUTO":
            detected = find_auto_port()
            if detected:
                if not (_reader_thread and _reader_thread.is_alive()):
                    start_serial_reader(port=port, baud_rate=baud)
            else:
                if _reader_thread and _reader_thread.is_alive():
                    stop_serial_reader()
                return JsonResponse({
                    "status": "disconnected",
                    "weight": "0.000",
                    "unit": "kg",
                    "error": "No USB-to-Serial device connected.",
                    "timestamp": timezone.localtime().isoformat(),
                    "platform": sys.platform,
                })
        else:
            if not (_reader_thread and _reader_thread.is_alive()):
                start_serial_reader(port=port, baud_rate=baud)

        data = get_latest_weight()
        if not data.get("timestamp"):
            data["timestamp"] = timezone.localtime().isoformat()
        return JsonResponse(data)


class ListPortsView(View):
    """GET /api/scale/ports/ — lists serial ports visible to the OS (debug helper)."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        return JsonResponse({
            "scale_enabled": getattr(settings, "SCALE_ENABLED", True),
            "platform": sys.platform,
            "ports": list_available_ports(),
        })
