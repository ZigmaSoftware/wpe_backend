"""
Background serial reader for the Point Digi Scale indicator.

Supports auto-detection of the QinHeng CH340 USB-to-Serial converter
(VID 1A86 / PID 7523) used by the Point Digi scale.  Set SERIAL_PORT='AUTO'
(the default) to let the reader find the device itself, or set a fixed port
name such as '/dev/ttyUSB0' or 'COM3' to bypass detection.
"""

import re
import sys
import threading
import logging
from datetime import datetime, timezone

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)

CH340_VID = 0x1A86
CH340_PID = 0x7523

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


def get_latest_weight() -> dict:
    with _lock:
        return dict(_latest_weight)


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
                    active_port = find_ch340_port()
                    if active_port is None:
                        _update_state(
                            status="disconnected",
                            error=(
                                f"CH340 device (VID=1A86, PID=7523) not found on {sys.platform}. "
                                "Connect the USB cable and wait…"
                            ),
                            detected_port=None,
                        )
                        _stop_event.wait(timeout=retry_delay)
                        continue
                else:
                    active_port = port

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
            logger.warning("Serial error on %s: %s", active_port, exc)
            if ser and ser.is_open:
                ser.close()
            ser = None
            if port == "AUTO":
                active_port = None
            _update_state(status="disconnected", error=str(exc), detected_port=active_port)
            _stop_event.wait(timeout=retry_delay)

        except Exception as exc:
            logger.exception("Unexpected error in serial reader: %s", exc)
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
        _latest_weight["timestamp"] = datetime.now(timezone.utc).isoformat()
