import sys

from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from django.conf import settings

from .serial_reader import get_disabled_weight, get_latest_weight, list_available_ports


class LatestWeightView(View):
    """GET /api/scale/weight/latest/ — returns most recent reading from serial port."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        if not getattr(settings, "SCALE_ENABLED", True):
            return JsonResponse(get_disabled_weight())

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
