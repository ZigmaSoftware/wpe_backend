import json
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from . import serial_manager


class PortsView(View):
    """GET /api/weighscale/ports/ — enumerate serial ports on the host."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        return JsonResponse({"ports": serial_manager.list_ports()})


@method_decorator(csrf_exempt, name="dispatch")
class ConnectView(View):
    """POST /api/weighscale/connect/ — open port and start serial reader thread."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"message": "Invalid JSON body"}, status=400)

        port = str(data.get("port", "")).strip()
        baud_rate = data.get("baud_rate", 9600)
        try:
            baud_rate = int(baud_rate)
        except (TypeError, ValueError):
            baud_rate = 9600

        if not port:
            return JsonResponse({"message": "port is required"}, status=400)

        if serial_manager.is_connected():
            return JsonResponse(
                {"message": f"Port {serial_manager.get_active_port()} is already open"},
                status=409,
            )

        ok, error = serial_manager.connect(port, baud_rate)
        if not ok:
            return JsonResponse({"message": error or "Failed to open port"}, status=500)

        return JsonResponse({"ok": True, "port": port, "baud_rate": baud_rate})


@method_decorator(csrf_exempt, name="dispatch")
class DisconnectView(View):
    """POST /api/weighscale/disconnect/ — close active serial port."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        if not serial_manager.is_connected():
            return JsonResponse({"message": "No port is currently open"}, status=400)

        serial_manager.disconnect()
        return JsonResponse({"ok": True})
