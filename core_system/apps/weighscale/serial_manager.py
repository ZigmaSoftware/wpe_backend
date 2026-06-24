"""
Serial port manager for the weighscale WebSocket integration.

Exposes connect/disconnect/list_ports.
On each complete line from the serial port, broadcasts a weight reading
to all connected WebSocket clients via Django Channels group 'weighscale_live'.
"""

import re
import threading
import logging

import serial
import serial.tools.list_ports
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

logger = logging.getLogger(__name__)

CHANNEL_GROUP = "weighscale_live"

_lock = threading.Lock()
_serial: serial.Serial | None = None
_reader_thread: threading.Thread | None = None
_stop_event = threading.Event()
_active_port: str | None = None


CH340_VID = 0x1A86
CH340_PID = 0x7523


def list_ports() -> list[dict]:
    return [
        {
            "device": p.device,
            "description": p.description or "",
            "manufacturer": p.manufacturer or "",
            "hwid": p.hwid or "",
        }
        for p in serial.tools.list_ports.comports()
    ]


def auto_connect(port_setting: str = "AUTO", baud_rate: int = 9600) -> tuple[bool, str | None]:
    """
    Try to connect using SERIAL_PORT / SERIAL_BAUD_RATE from settings.
    If port_setting is AUTO, probe for CH340 first, then any USB/ACM port.
    Returns (True, None) if already connected or newly connected.
    """
    with _lock:
        if _serial is not None and _serial.is_open:
            return True, None

    if port_setting == "AUTO":
        target = _find_auto_port()
        if target is None:
            return False, "No suitable USB serial port detected on this host."
    else:
        target = port_setting

    return connect(target, baud_rate)


def _find_auto_port() -> str | None:
    available = list(serial.tools.list_ports.comports())
    if not available:
        return None

    for p in available:
        if p.vid == CH340_VID and p.pid == CH340_PID:
            logger.info("Auto-connect: CH340 found at %s", p.device)
            return p.device

    for p in available:
        device = p.device or ""
        if sys.platform.startswith("linux"):
            if device.startswith("/dev/ttyUSB") or device.startswith("/dev/ttyACM"):
                logger.info("Auto-connect: USB serial found at %s", p.device)
                return p.device
        elif sys.platform == "darwin":
            meta = " ".join(str(v or "").lower() for v in (device, p.description, p.manufacturer))
            if "usbserial" in meta or "usb" in meta:
                return p.device
        elif sys.platform == "win32":
            if device.upper().startswith("COM"):
                return p.device

    return None


def is_connected() -> bool:
    with _lock:
        return _serial is not None and _serial.is_open


def get_active_port() -> str | None:
    with _lock:
        return _active_port


def connect(port: str, baud_rate: int = 9600) -> tuple[bool, str | None]:
    global _serial, _reader_thread, _active_port, _stop_event

    with _lock:
        if _serial is not None and _serial.is_open:
            return False, "already_open"

    try:
        ser = serial.Serial(
            port=port,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1,
        )
    except serial.SerialException as exc:
        msg = str(exc)
        if "[Errno 13]" in msg or "permission denied" in msg.lower():
            msg = f"{msg} — Permission denied. Add user to dialout group: sudo usermod -aG dialout $USER"
        return False, msg
    except Exception as exc:
        return False, str(exc)

    with _lock:
        _serial = ser
        _active_port = port
        _stop_event = threading.Event()

    _reader_thread = threading.Thread(
        target=_read_loop,
        name="WeighscaleReaderThread",
        daemon=True,
    )
    _reader_thread.start()
    logger.info("Weighscale serial connected: port=%s baud=%d", port, baud_rate)
    return True, None


def disconnect() -> bool:
    global _serial, _active_port

    with _lock:
        if _serial is None or not _serial.is_open:
            return False
        ser = _serial
        _serial = None
        _active_port = None

    _stop_event.set()
    try:
        ser.close()
    except Exception:
        pass

    _broadcast("disconnected", reason="explicit_disconnect")
    logger.info("Weighscale serial disconnected.")
    return True


def parse_weight(raw_line: str) -> dict | None:
    line = raw_line.strip()
    if not line:
        return None

    upper = line.upper()

    # Stability: stable if ST or GS present, or no explicit unstable flag
    stable = ("ST" in upper or "GS" in upper) or ("US" not in upper and "UNSTABLE" not in upper)

    # Extract unit (prefer unit adjacent to number)
    unit = "kg"
    unit_match = re.search(r"\b(KG|G\b|LBS|LB|T\b)\b", upper)
    if unit_match:
        unit_map = {"KG": "kg", "G": "g", "LBS": "lb", "LB": "lb", "T": "t"}
        unit = unit_map.get(unit_match.group(1), "kg")

    # Extract first float-like value (handles +/- prefix and spaces)
    num_match = re.search(r"[+-]?\s*(\d+\.?\d*)", line)
    if num_match:
        try:
            weight_val = float(num_match.group(0).replace(" ", ""))
            return {"weight": weight_val, "unit": unit, "stable": stable}
        except ValueError:
            pass

    return None


def _broadcast(event: str, **data) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    payload = {"type": "weighscale.message", "event": event, **data}
    try:
        async_to_sync(channel_layer.group_send)(CHANNEL_GROUP, payload)
    except Exception as exc:
        logger.debug("Broadcast error: %s", exc)


def _read_loop() -> None:
    buffer = b""

    while not _stop_event.is_set():
        with _lock:
            ser = _serial

        if ser is None or not ser.is_open:
            break

        try:
            chunk = ser.read(256)
            if not chunk:
                continue

            buffer += chunk

            # Process complete lines
            while True:
                found = False
                for terminator in (b"\r\n", b"\r", b"\n"):
                    idx = buffer.find(terminator)
                    if idx >= 0:
                        raw_bytes = buffer[:idx]
                        buffer = buffer[idx + len(terminator):]
                        raw_line = raw_bytes.decode("utf-8", errors="replace").strip()
                        if raw_line:
                            _process_line(raw_line)
                        found = True
                        break
                if not found:
                    break

        except serial.SerialException as exc:
            logger.warning("Weighscale serial error: %s", exc)
            with _lock:
                if _serial:
                    try:
                        _serial.close()
                    except Exception:
                        pass
                globals()["_serial"] = None
                globals()["_active_port"] = None
            _broadcast("disconnected", reason="device_removed")
            break

        except Exception as exc:
            logger.exception("Weighscale read loop error: %s", exc)
            break

    logger.info("Weighscale read loop exited.")


def _process_line(raw_line: str) -> None:
    parsed = parse_weight(raw_line)
    if parsed:
        _broadcast(
            "weight",
            raw=raw_line,
            weight=parsed["weight"],
            unit=parsed["unit"],
            stable=parsed["stable"],
            timestamp=timezone.now().isoformat(),
        )
    else:
        logger.debug("Unparseable serial line: %r", raw_line)
