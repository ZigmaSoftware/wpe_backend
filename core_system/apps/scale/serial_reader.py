from __future__ import annotations

import logging
import sys
import time
from datetime import timedelta
from typing import Any

import serial
import serial.tools.list_ports
from django.conf import settings
from django.utils import timezone

from apps.weighscale import serial_manager


logger = logging.getLogger(__name__)

CH340_VID = 0x1A86
CH340_PID = 0x7523
FAILED_PORT_COOLDOWN_SECONDS = 30
NO_PORT_WARNING_INTERVAL_SECONDS = 60
SCALE_DISABLED_ERROR = "Server-side scale serial reading is disabled."

READING_STATUSES = {"connected", "stable", "unstable", "invalid_reading"}
_failed_ports_until: dict[str, float] = {}
_last_no_port_warning_at = 0.0


def _now_iso() -> str:
    return timezone.now().isoformat()


def _payload(
    *,
    status: str,
    weight: Any = "0.000",
    unit: str = "kg",
    stable: bool | None = None,
    error: str | None = None,
    raw_data: str = "",
    timestamp: str | None = None,
    last_seen_at: str | None = None,
    detected_port: str | None = None,
) -> dict[str, Any]:
    captured_at = timestamp or _now_iso()
    return {
        "status": status,
        "weight": f"{float(weight or 0):.3f}",
        "unit": unit or "kg",
        "stable": stable,
        "source": "server_serial",
        "error": error,
        "raw_data": raw_data or "",
        "timestamp": captured_at,
        "captured_at": captured_at,
        "last_seen_at": last_seen_at or captured_at,
        "detected_port": detected_port,
        "platform": sys.platform,
    }


def get_disabled_weight() -> dict[str, Any]:
    return _payload(
        status="disconnected",
        error=SCALE_DISABLED_ERROR,
        detected_port=serial_manager.get_active_port(),
    )


def _port_in_cooldown(device: str) -> bool:
    cooldown_until = _failed_ports_until.get(device)
    if cooldown_until is None:
        return False
    if cooldown_until <= time.monotonic():
        _failed_ports_until.pop(device, None)
        return False
    return True


def _mark_port_failed(device: str) -> None:
    if device:
        _failed_ports_until[device] = time.monotonic() + FAILED_PORT_COOLDOWN_SECONDS


def _is_ch340(port: Any) -> bool:
    return getattr(port, "vid", None) == CH340_VID and getattr(port, "pid", None) == CH340_PID


def is_candidate_port(port: Any) -> bool:
    if _is_ch340(port):
        return True

    device = str(getattr(port, "device", "") or "")
    metadata = " ".join(
        str(value or "").lower()
        for value in (
            getattr(port, "description", ""),
            getattr(port, "manufacturer", ""),
            getattr(port, "product", ""),
            getattr(port, "interface", ""),
            getattr(port, "hwid", ""),
        )
    )

    if sys.platform.startswith("linux"):
        return device.startswith("/dev/ttyUSB") or device.startswith("/dev/ttyACM")
    if sys.platform == "win32":
        return device.upper().startswith("COM")
    if sys.platform == "darwin":
        return device.startswith("/dev/tty.") or device.startswith("/dev/cu.")
    return any(token in metadata for token in ("usb", "serial", "uart", "ch340", "cp210", "ftdi"))


def find_auto_port() -> str | None:
    ports = list(serial.tools.list_ports.comports())
    candidates = [port for port in ports if is_candidate_port(port)]
    available = [port for port in candidates if not _port_in_cooldown(str(getattr(port, "device", "") or ""))]

    preferred = [port for port in available if _is_ch340(port)]
    selected = (preferred or available)
    if selected:
        port = selected[0]
        logger.info(
            "Selected scale serial port: device=%s description=%s vid=%s pid=%s",
            getattr(port, "device", ""),
            getattr(port, "description", ""),
            getattr(port, "vid", None),
            getattr(port, "pid", None),
        )
        return str(getattr(port, "device", "") or "") or None

    global _last_no_port_warning_at
    now = time.monotonic()
    if now - _last_no_port_warning_at >= NO_PORT_WARNING_INTERVAL_SECONDS:
        _last_no_port_warning_at = now
        logger.warning(
            "No candidate scale serial port found. visible_ports=%s",
            [
                {
                    "device": getattr(port, "device", ""),
                    "description": getattr(port, "description", ""),
                    "vid": getattr(port, "vid", None),
                    "pid": getattr(port, "pid", None),
                }
                for port in ports
            ],
        )
    return None


def _connect_if_needed() -> tuple[bool, str | None, str | None]:
    if serial_manager.is_connected():
        return True, None, serial_manager.get_active_port()

    configured_port = str(getattr(settings, "SERIAL_PORT", "AUTO") or "AUTO").strip() or "AUTO"
    baud_rate = int(getattr(settings, "SERIAL_BAUD_RATE", 9600))
    target_port = find_auto_port() if configured_port.upper() == "AUTO" else configured_port

    if not target_port:
        return False, "No serial port detected on this backend host.", None

    logger.info("Opening scale indicator serial port: port=%s baud_rate=%s", target_port, baud_rate)
    ok, error = serial_manager.connect(target_port, baud_rate)
    if ok or error == "already_open":
        return True, None, target_port

    _mark_port_failed(target_port)
    return False, error or "Unable to open serial port.", target_port


def _parse_datetime(value: Any):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value
    try:
        return timezone.datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _normalize_latest(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _payload(
        status=str(payload.get("status") or "disconnected"),
        weight=payload.get("weight", "0.000"),
        unit=str(payload.get("unit") or "kg"),
        stable=payload.get("stable"),
        error=payload.get("error"),
        raw_data=str(payload.get("raw_data") or payload.get("raw") or ""),
        timestamp=payload.get("timestamp") or payload.get("captured_at"),
        last_seen_at=payload.get("last_seen_at") or payload.get("timestamp") or payload.get("captured_at"),
        detected_port=payload.get("detected_port") or serial_manager.get_active_port(),
    )

    last_seen_at = _parse_datetime(normalized.get("last_seen_at"))
    stale_after_seconds = int(getattr(settings, "SCALE_STALE_AFTER_SECONDS", 5))
    if normalized["status"] in READING_STATUSES and last_seen_at is not None:
        if timezone.is_naive(last_seen_at):
            last_seen_at = timezone.make_aware(last_seen_at, timezone.get_current_timezone())
        if timezone.now() - last_seen_at > timedelta(seconds=stale_after_seconds):
            return _payload(
                status="disconnected",
                weight=normalized["weight"],
                unit=normalized["unit"],
                stable=normalized["stable"],
                error="No fresh server-side scale reading received within stale threshold.",
                raw_data=normalized["raw_data"],
                timestamp=normalized["timestamp"],
                last_seen_at=normalized["last_seen_at"],
                detected_port=normalized["detected_port"],
            )

    return normalized


def get_latest_weight() -> dict[str, Any]:
    if not getattr(settings, "SCALE_ENABLED", True):
        return get_disabled_weight()

    try:
        ok, error, detected_port = _connect_if_needed()
        latest = serial_manager.get_latest_payload()
        if not ok:
            status = "no_serial_port" if detected_port is None else "error"
            return _payload(status=status, error=error, detected_port=detected_port)
        if latest is None:
            return _payload(status="disconnected", error="Serial port connected, waiting for reading.", detected_port=detected_port)
        return _normalize_latest(latest)
    except Exception as exc:
        logger.exception("Server-side scale serial read failed: %s", exc)
        return _payload(status="error", error=str(exc), detected_port=serial_manager.get_active_port())
