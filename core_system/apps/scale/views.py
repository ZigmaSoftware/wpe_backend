import sys
from datetime import datetime, timezone

from django.http import JsonResponse
from django.views import View

from .serial_reader import get_latest_weight, list_available_ports


class LatestWeightView(View):
    """GET /api/scale/weight/latest/ — returns most recent reading from serial port."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        data = get_latest_weight()
        if not data.get("timestamp"):
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
        return JsonResponse(data)


class ListPortsView(View):
    """GET /api/scale/ports/ — lists serial ports visible to the OS (debug helper)."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        return JsonResponse({
            "platform": sys.platform,
            "ports": list_available_ports(),
        })
