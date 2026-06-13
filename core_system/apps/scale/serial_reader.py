"""
Background serial reader for the Point Digi Scale indicator.

Serial port is configured via environment variables (read through Django settings):
  SCALE_ENABLED=false     Disable the serial reader entirely and return a
                          disconnected API payload without probing ports.
  SERIAL_PORT=AUTO        Scan all available serial ports; prefers the CH340
                          USB-to-Serial converter (VID 1A86 / PID 7523) but
                          falls back to the first available port on the system.
  SERIAL_PORT=COM4        Use the specified port directly (Windows).
  SERIAL_PORT=/dev/ttyUSB0  Use the specified port directly (Linux/macOS).
  SERIAL_BAUD_RATE=9600   Baud rate (default 9600).
"""

import re
import sys
import threading
import logging
import time

import serial
import serial.tools.list_ports
from django.utils import timezone as django_timezone

logger = logging.getLogger(__name__)

CH340_VID = 0x1A86
CH340_PID = 0x7523
FAILED_PORT_COOLDOWN_SECONDS = 15
NO_PORT_WARNING_INTERVAL_SECONDS = 300
SCALE_DISABLED_ERROR = "Scale integration is disabled by configuration."

_PLATFORM_FALLBACKS = {
    "linux":  "/dev/ttyUSB0",
    "win32":  "COM3",
    "darwin": "/dev/tty.wchusbserial-0001",
}

_lock = threading.Lock()
_latest_weight = {
    "raw_data":      "",
    "weight":        "0.000",
    "unit":          "kg",
    "status":        "disconnected",
    "timestamp":     None,
    "error":         None,
    "detected_port": None,
    "platform":      sys.platform,
}
_reader_thread = None
_stop_event    = threading.Event()
_failed_ports_until: dict[str, float] = {}
_last_no_port_warning_at = 0.0


def build_scale_state(
    *,
    raw_data: str = "",
    weight: str = "0.000",
    unit: str = "kg",
    status: str = "disconnected",
    error: str | None = None,
    detected_port: str | None = None,
) -> dict:
    return {
        "raw_data": raw_data,
        "weight": weight,
        "unit": unit,
        "status": status,
        "timestamp": django_timezone.localtime().isoformat(),
        "error": error,
        "detected_port": detected_port,
        "platform": sys.platform,
    }


def get_latest_weight() -> dict:
    with _lock:
        return dict(_latest_weight)


def get_disabled_weight() -> dict:
    return build_scale_state(error=SCALE_DISABLED_ERROR)


def set_scale_disabled() -> None:
    with _lock:
        _latest_weight.update(get_disabled_weight())


def find_ch340_port() -> str | None:
    for port in serial.tools.list_ports.comports():
        if port.vid == CH340_VID and port.pid == CH340_PID:
            logger.info("CH340 found: %s — %s", port.device, port.description)
            return port.device

    available = [
        f"{p.device} (VID={hex(p.vid or 0)} PID={hex(p.pid or 0)})"
        for p in serial.tools.list_ports.comports()
    ]
    logger.debug("CH340 not found. Available ports: %s", available or ["none"])
    return None


def list_available_ports() -> list[dict]:
    return [
        {
            "device":      p.device,
            "description": p.description or "",
            "vid":         hex(p.vid) if p.vid else None,
            "pid":         hex(p.pid) if p.pid else None,
            "serial_no":   p.serial_number or "",
            "is_ch340":    (p.vid == CH340_VID and p.pid == CH340_PID),
        }
        for p in serial.tools.list_ports.comports()
    ]


def get_platform_default_port() -> str:
    return _PLATFORM_FALLBACKS.get(sys.platform, "/dev/ttyUSB0")


def _port_metadata(port) -> str:
    return " ".join(
        str(value or "").strip().lower()
        for value in (
            getattr(port, "device", ""),
            getattr(port, "description", ""),
            getattr(port, "manufacturer", ""),
            getattr(port, "product", ""),
            getattr(port, "interface", ""),
            getattr(port, "hwid", ""),
        )
        if str(value or "").strip()
    )


def is_candidate_scale_port(port) -> bool:
    if port.vid == CH340_VID and port.pid == CH340_PID:
        return True

    device = str(getattr(port, "device", "") or "").strip()
    metadata = _port_metadata(port)

    if sys.platform.startswith("linux"):
        return device.startswith("/dev/ttyUSB") or device.startswith("/dev/ttyACM") or "/dev/serial/" in device

    if sys.platform == "darwin":
        return (
            device.startswith("/dev/tty.usb")
            or device.startswith("/dev/cu.usb")
            or "wch" in metadata
            or "usbserial" in metadata
        )

    if sys.platform == "win32":
        return device.upper().startswith("COM")

    return any(keyword in metadata for keyword in ("usb", "serial", "uart", "ch340", "ftdi", "cp210", "pl2303"))


def _prune_failed_ports() -> None:
    now = time.monotonic()
    expired_ports = [port for port, retry_after in _failed_ports_until.items() if retry_after <= now]
    for port in expired_ports:
        _failed_ports_until.pop(port, None)


def _is_port_in_cooldown(port: str | None) -> bool:
    if not port:
        return False
    _prune_failed_ports()
    retry_after = _failed_ports_until.get(port)
    return retry_after is not None and retry_after > time.monotonic()


def _mark_port_failed(port: str | None) -> None:
    if not port:
        return
    _failed_ports_until[port] = time.monotonic() + FAILED_PORT_COOLDOWN_SECONDS


def _warn_no_ports_once(message: str, *args) -> None:
    global _last_no_port_warning_at

    now = time.monotonic()
    if now - _last_no_port_warning_at < NO_PORT_WARNING_INTERVAL_SECONDS:
        return

    logger.warning(message, *args)
    _last_no_port_warning_at = now


def find_auto_port() -> str | None:
    """
    Detect an available serial port for AUTO mode.

    Priority:
    1. CH340 USB-to-Serial converter identified by VID/PID (most reliable).
    2. First USB/ACM-style serial port that looks like a real external adapter.

    Returns the port device string (e.g. 'COM4', '/dev/ttyUSB0') or None.
    """
    available = list(serial.tools.list_ports.comports())
    if not available:
        _warn_no_ports_once(
            "AUTO: No serial ports found on %s. "
            "Connect the USB-to-Serial device and wait, or set SERIAL_PORT explicitly in .env.",
            sys.platform,
        )
        return None

    preferred_ports = [port for port in available if port.vid == CH340_VID and port.pid == CH340_PID]
    for port in preferred_ports:
        if _is_port_in_cooldown(port.device):
            continue
        logger.info("AUTO: Using CH340 port %s (%s).", port.device, port.description or "no description")
        return port.device

    candidates = [port for port in available if is_candidate_scale_port(port) and not _is_port_in_cooldown(port.device)]
    if not candidates:
        _warn_no_ports_once(
            "AUTO: No suitable external serial ports available on %s. Visible ports: %s",
            sys.platform,
            [port.device for port in available] or ["none"],
        )
        return None

    chosen = candidates[0].device
    logger.info(
        "AUTO: CH340 not found. Using candidate port: %s (%s).",
        chosen,
        candidates[0].description or "no description",
    )
    if len(candidates) > 1:
        logger.debug(
            "AUTO: Other candidate ports (not selected): %s",
            [p.device for p in candidates[1:]],
        )
    return chosen


def start_serial_reader(port: str = "AUTO", baud_rate: int = 9600) -> None:
    global _reader_thread, _stop_event

    if _reader_thread and _reader_thread.is_alive():
        logger.info("Serial reader already running.")
        return

    _stop_event.clear()
    _reader_thread = threading.Thread(
        target=_read_loop,
        args=(port, baud_rate),
        name="SerialReaderThread",
        daemon=True,
    )
    _reader_thread.start()
    logger.info("Serial reader started. port=%r baud=%d platform=%s", port, baud_rate, sys.platform)


def stop_serial_reader() -> None:
    _stop_event.set()
    if _reader_thread:
        _reader_thread.join(timeout=5)
    logger.info("Serial reader stopped.")


def parse_weight_data(raw_line: str) -> dict | None:
    line  = raw_line.strip()
    if not line:
        return None

    upper = line.upper()

    if upper.startswith("OL") or "OVERLOAD" in upper:
        status = "overload"
    elif upper.startswith("US,") or upper.startswith("US "):
        status = "unstable"
    elif upper.startswith("ST,") or upper.startswith("ST "):
        status = "stable"
    else:
        status = "stable"

    match = re.search(r"([+-]?\s*\d+\.?\d*)\s*(KG|LBS|LB|OZ|T\b|G\b)", upper)
    if match:
        weight_str = match.group(1).replace(" ", "")
        unit_map   = {"KG": "kg", "LBS": "lb", "LB": "lb", "OZ": "oz", "T": "t", "G": "g"}
        unit       = unit_map.get(match.group(2), match.group(2).lower())
        try:
            return {"weight": f"{float(weight_str):.3f}", "unit": unit, "status": status}
        except ValueError:
            pass

    num_match = re.search(r"([+-]?\s*\d+\.?\d*)", line)
    if num_match:
        weight_str = num_match.group(1).replace(" ", "")
        try:
            return {"weight": f"{float(weight_str):.3f}", "unit": "kg", "status": status}
        except ValueError:
            pass

    logger.debug("Could not parse line: %r", raw_line)
    return None


def _read_loop(port: str, baud_rate: int) -> None:
    ser         = None
    retry_delay = 3
    active_port = None

    while not _stop_event.is_set():
        try:
            if ser is None or not ser.is_open:
                if port == "AUTO":
                    active_port = find_auto_port()
                    if active_port is None:
                        _update_state(
                            status="disconnected",
                            error=(
                                f"No serial port found on {sys.platform}. "
                                "Connect the USB-to-Serial device and wait, "
                                "or set SERIAL_PORT=<port> in .env to specify a port explicitly."
                            ),
                            detected_port=None,
                        )
                        _stop_event.wait(timeout=retry_delay)
                        retry_delay = min(retry_delay * 2, 60)
                        continue
                else:
                    active_port = port
                    if _is_port_in_cooldown(active_port):
                        _update_state(
                            status="disconnected",
                            error=f"Serial port {active_port} is temporarily unavailable. Retrying shortly.",
                            detected_port=active_port,
                        )
                        _stop_event.wait(timeout=retry_delay)
                        retry_delay = min(retry_delay * 2, 60)
                        continue

                logger.info("Opening %s at %d baud…", active_port, baud_rate)
                ser = serial.Serial(
                    port=active_port,
                    baudrate=baud_rate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1,
                )
                logger.info("Opened %s successfully.", active_port)
                retry_delay = 3
                _update_state(status="connected", error=None, detected_port=active_port)

            raw_bytes = ser.readline()
            if not raw_bytes:
                continue

            raw_line = raw_bytes.decode("utf-8", errors="replace").strip()
            if not raw_line:
                continue

            logger.debug("RX [%s]: %r", active_port, raw_line)

            parsed = parse_weight_data(raw_line)
            if parsed:
                _update_state(
                    raw_data=raw_line,
                    weight=parsed["weight"],
                    unit=parsed["unit"],
                    status=parsed["status"],
                    error=None,
                    detected_port=active_port,
                )
            else:
                _update_state(raw_data=raw_line, detected_port=active_port)

        except serial.SerialException as exc:
            exc_lower = str(exc).lower()
            if "in use" in exc_lower or "access denied" in exc_lower or "permissionerror" in exc_lower:
                logger.warning("Port %s is already in use: %s", active_port, exc)
            elif "could not open port" in exc_lower or "not found" in exc_lower or "no such" in exc_lower:
                logger.warning("Invalid or unavailable port %s: %s", active_port, exc)
            elif (
                "device disconnected" in exc_lower
                or "ioerror" in exc_lower
                or "errno 5" in exc_lower
                or "input/output error" in exc_lower
            ):
                logger.warning("Device disconnected from %s: %s", active_port, exc)
            else:
                logger.warning("Serial error on %s: %s", active_port, exc)
            if ser and ser.is_open:
                ser.close()
            _mark_port_failed(active_port)
            ser = None
            if port == "AUTO":
                active_port = None
            _update_state(status="disconnected", error=str(exc), detected_port=active_port)
            _stop_event.wait(timeout=retry_delay)

        except Exception as exc:
            logger.exception("Unable to read data from %s: %s", active_port, exc)
            if ser and ser.is_open:
                ser.close()
            ser = None
            if port == "AUTO":
                active_port = None
            _update_state(status="error", error=str(exc), detected_port=active_port)
            _stop_event.wait(timeout=retry_delay)

    if ser and ser.is_open:
        ser.close()
    logger.info("Serial read loop exited cleanly.")


def _update_state(**kwargs) -> None:
    with _lock:
        _latest_weight.update(kwargs)
        _latest_weight["timestamp"] = django_timezone.localtime().isoformat()
