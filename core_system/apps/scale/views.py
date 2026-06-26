import json
import logging
import sys
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import hmac

from . import serial_reader
from .models import ScaleBridgeReading

logger = logging.getLogger(__name__)

BRIDGE_STATUSES = {
    ScaleBridgeReading.Status.CONNECTED,
    ScaleBridgeReading.Status.STABLE,
    ScaleBridgeReading.Status.UNSTABLE,
    ScaleBridgeReading.Status.DISCONNECTED,
    ScaleBridgeReading.Status.ERROR,
    ScaleBridgeReading.Status.NO_SERIAL_PORT,
    ScaleBridgeReading.Status.INVALID_READING,
    ScaleBridgeReading.Status.BRIDGE_NOT_REPORTING,
}


def _bridge_api_key_is_valid(request) -> bool:
    configured_key = getattr(settings, "SCALE_BRIDGE_API_KEY", "").strip()
    if not configured_key:
        return False
    provided_key = request.headers.get("X-Bridge-API-Key", "").strip()
    return bool(provided_key) and hmac.compare_digest(provided_key, configured_key)


def _json_error(message: str, *, status_code: int, **extra: Any) -> JsonResponse:
    payload = {"status": "error", "error": message, **extra}
    return JsonResponse(payload, status=status_code)


def _parse_payload(request) -> dict[str, Any]:
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


def _parse_decimal_weight(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.001"))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _parse_captured_at(value: Any):
    parsed = parse_datetime(str(value)) if value not in (None, "") else None
    if parsed is None:
        return timezone.now()
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _build_bridge_payload(reading: ScaleBridgeReading, *, stale: bool) -> dict[str, Any]:
    if stale:
        return {
            "status": ScaleBridgeReading.Status.BRIDGE_NOT_REPORTING,
            "error": (
                f"No latest reading received from local bridge for device "
                f"{reading.device_id} at workstation {reading.workstation_id}."
            ),
            "device_id": reading.device_id,
            "workstation_id": reading.workstation_id,
            "weight": f"{Decimal(reading.weight or 0):.3f}",
            "unit": reading.unit or "kg",
            "source": reading.source or "local_bridge",
            "raw_data": reading.raw_value or "",
            "captured_at": reading.captured_at.isoformat() if reading.captured_at else None,
            "last_seen_at": reading.last_seen_at.isoformat() if reading.last_seen_at else None,
            "detected_port": reading.detected_port or None,
            "platform": sys.platform,
        }

    return {
        "status": reading.status,
        "error": reading.error or None,
        "device_id": reading.device_id,
        "workstation_id": reading.workstation_id,
        "weight": f"{Decimal(reading.weight or 0):.3f}",
        "unit": reading.unit or "kg",
        "source": reading.source or "local_bridge",
        "raw_data": reading.raw_value or "",
        "captured_at": reading.captured_at.isoformat() if reading.captured_at else None,
        "timestamp": reading.captured_at.isoformat() if reading.captured_at else None,
        "last_seen_at": reading.last_seen_at.isoformat() if reading.last_seen_at else None,
        "detected_port": reading.detected_port or None,
        "platform": sys.platform,
    }


def _get_bridge_reading(*, device_id: str | None, workstation_id: str | None) -> ScaleBridgeReading | None:
    queryset = ScaleBridgeReading.objects.all()
    if device_id and workstation_id:
        return queryset.filter(device_id=device_id, workstation_id=workstation_id).first()
    if device_id:
        return queryset.filter(device_id=device_id).first()
    if workstation_id:
        return queryset.filter(workstation_id=workstation_id).order_by("-last_seen_at", "device_id").first()
    return None


class LatestWeightView(View):
    """GET /api/scale/weight/latest/ — returns latest bridge reading."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        device_id = str(request.GET.get("device_id") or "").strip() or None
        workstation_id = str(request.GET.get("workstation_id") or "").strip() or None

        if device_id is None and workstation_id is None:
            return JsonResponse(serial_reader.get_latest_weight())

        reading = _get_bridge_reading(device_id=device_id, workstation_id=workstation_id)
        if reading is None:
            logger.info(
                "Scale bridge latest requested but no reading exists: device_id=%s workstation_id=%s",
                device_id or "",
                workstation_id or "",
            )
            return JsonResponse({
                "status": ScaleBridgeReading.Status.BRIDGE_NOT_REPORTING,
                "error": "No reading received from local bridge for the selected device/workstation.",
                "device_id": device_id,
                "workstation_id": workstation_id,
                "weight": "0.000",
                "unit": "kg",
                "source": "local_bridge",
                "last_seen_at": None,
                "platform": sys.platform,
            })

        stale_after_seconds = int(getattr(settings, "SCALE_BRIDGE_STALE_AFTER_SECONDS", 5))
        stale = timezone.now() - reading.last_seen_at > timedelta(seconds=stale_after_seconds)
        if stale:
            logger.warning(
                "Scale bridge reading is stale: device_id=%s workstation_id=%s last_seen_at=%s stale_after_seconds=%s",
                reading.device_id,
                reading.workstation_id,
                reading.last_seen_at.isoformat() if reading.last_seen_at else None,
                stale_after_seconds,
            )
        return JsonResponse(_build_bridge_payload(reading, stale=stale))


class ListPortsView(View):
    """GET /api/scale/ports/ — lists serial ports visible to the OS."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        import serial.tools.list_ports
        ports = [
            {
                "device": p.device,
                "description": p.description or "",
                "vid": hex(p.vid) if p.vid else None,
                "pid": hex(p.pid) if p.pid else None,
                "serial_no": p.serial_number or "",
            }
            for p in serial.tools.list_ports.comports()
        ]
        return JsonResponse({"platform": sys.platform, "ports": ports})


class ScaleBridgeDevicesView(View):
    """GET /api/scale/devices/ — lists bridge-registered weighing devices."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        stale_after_seconds = int(getattr(settings, "SCALE_BRIDGE_STALE_AFTER_SECONDS", 5))
        cutoff = timezone.now() - timedelta(seconds=stale_after_seconds)
        devices = []
        for reading in ScaleBridgeReading.objects.all().order_by("-last_seen_at", "device_id", "workstation_id"):
            effective_status = (
                ScaleBridgeReading.Status.BRIDGE_NOT_REPORTING
                if reading.last_seen_at < cutoff
                else reading.status
            )
            devices.append({
                "device_id": reading.device_id,
                "workstation_id": reading.workstation_id,
                "status": effective_status,
                "weight": f"{Decimal(reading.weight or 0):.3f}",
                "unit": reading.unit or "kg",
                "source": reading.source or "local_bridge",
                "last_seen_at": reading.last_seen_at.isoformat() if reading.last_seen_at else None,
                "captured_at": reading.captured_at.isoformat() if reading.captured_at else None,
                "detected_port": reading.detected_port or None,
                "error": reading.error or None,
            })
        return JsonResponse({"devices": devices})


@method_decorator(csrf_exempt, name="dispatch")
class ScaleBridgeReadingIngestView(View):
    """POST /api/scale/bridge/readings/ — accepts latest device reading from local bridge app."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        if not _bridge_api_key_is_valid(request):
            return _json_error("Invalid or missing bridge API key.", status_code=403)

        try:
            payload = _parse_payload(request)
        except json.JSONDecodeError:
            return _json_error("Request body must be valid JSON.", status_code=400)

        device_id = str(payload.get("device_id") or "").strip()
        workstation_id = str(payload.get("workstation_id") or "").strip()
        status = str(payload.get("status") or "").strip().lower()

        if not device_id:
            return _json_error("device_id is required.", status_code=400)
        if not workstation_id:
            return _json_error("workstation_id is required.", status_code=400)
        if status not in BRIDGE_STATUSES:
            return _json_error("status is invalid.", status_code=400)

        weight = _parse_decimal_weight(payload.get("weight"))
        statuses_requiring_weight = {
            ScaleBridgeReading.Status.CONNECTED,
            ScaleBridgeReading.Status.STABLE,
            ScaleBridgeReading.Status.UNSTABLE,
        }
        if status in statuses_requiring_weight and weight is None:
            return _json_error(
                "weight must be a valid decimal when status is connected, stable, or unstable.",
                status_code=400,
            )

        reading, _created = ScaleBridgeReading.objects.update_or_create(
            device_id=device_id,
            workstation_id=workstation_id,
            defaults={
                "weight": weight if weight is not None else Decimal("0.000"),
                "unit": str(payload.get("unit") or "kg").strip() or "kg",
                "status": status,
                "raw_value": str(payload.get("raw_value") or "").strip(),
                "source": str(payload.get("source") or "local_bridge").strip() or "local_bridge",
                "detected_port": str(payload.get("detected_port") or payload.get("serial_port") or "").strip(),
                "error": str(payload.get("error") or "").strip(),
                "captured_at": _parse_captured_at(payload.get("captured_at")),
                "last_seen_at": timezone.now(),
            },
        )

        if reading.status != ScaleBridgeReading.Status.CONNECTED:
            logger.info(
                "Scale bridge reported non-connected status: device_id=%s workstation_id=%s status=%s error=%s",
                reading.device_id,
                reading.workstation_id,
                reading.status,
                reading.error,
            )

        return JsonResponse({
            "ok": True,
            "device_id": reading.device_id,
            "workstation_id": reading.workstation_id,
            "status": reading.status,
            "last_seen_at": reading.last_seen_at.isoformat(),
        })
