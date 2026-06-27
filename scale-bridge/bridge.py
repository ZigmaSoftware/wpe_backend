from __future__ import annotations

import logging
import os
import platform
import re
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import dumps
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import serial
import serial.tools.list_ports
from dotenv import load_dotenv


CH340_VID = 0x1A86
CH340_PID = 0x7523
CONNECTED_STATUSES = {"connected", "stable", "unstable"}
RETRY_DELAY_SECONDS = 3
BRIDGE_ENV_PATH = Path(__file__).resolve().parent / ".env"


@dataclass
class BridgeConfig:
    server_url: str
    bridge_api_key: str
    device_id: str
    workstation_id: str
    serial_port: str
    serial_baud_rate: int
    push_interval_ms: int
    stale_after_seconds: int
    identity_host: str
    identity_port: int


@dataclass
class BridgeState:
    status: str = "disconnected"
    weight: str = "0.000"
    unit: str = "kg"
    raw_value: str = ""
    error: str = ""
    detected_port: str | None = None
    captured_at: datetime | None = None


def load_config() -> BridgeConfig:
    load_dotenv(BRIDGE_ENV_PATH, override=True)
    config = BridgeConfig(
        server_url=os.getenv("WPE_SERVER_URL", "").strip().rstrip("/"),
        bridge_api_key=os.getenv("SCALE_BRIDGE_API_KEY", os.getenv("BRIDGE_API_KEY", "")).strip(),
        device_id=os.getenv("DEVICE_ID", "").strip(),
        workstation_id=os.getenv("WORKSTATION_ID", "").strip(),
        serial_port=os.getenv("SERIAL_PORT", "AUTO").strip() or "AUTO",
        serial_baud_rate=int(os.getenv("SERIAL_BAUD_RATE", "9600")),
        push_interval_ms=max(200, int(os.getenv("PUSH_INTERVAL_MS", "500"))),
        stale_after_seconds=max(2, int(os.getenv("STALE_AFTER_SECONDS", "5"))),
        identity_host=os.getenv("LOCAL_IDENTITY_HOST", "127.0.0.1").strip() or "127.0.0.1",
        identity_port=max(0, int(os.getenv("LOCAL_IDENTITY_PORT", "8765"))),
    )
    missing = [
        name
        for name, value in (
            ("WPE_SERVER_URL", config.server_url),
            ("SCALE_BRIDGE_API_KEY", config.bridge_api_key),
            ("DEVICE_ID", config.device_id),
            ("WORKSTATION_ID", config.workstation_id),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")
    return config


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


class LocalIdentityHandler(BaseHTTPRequestHandler):
    config: BridgeConfig

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/", "/identity"}:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":false,"error":"not_found"}')
            return

        body = dumps({
            "ok": True,
            "device_id": self.config.device_id,
            "workstation_id": self.config.workstation_id,
            "serial_port": self.config.serial_port,
            "serial_baud_rate": self.config.serial_baud_rate,
            "server_url": self.config.server_url,
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        logging.debug("Local identity request: " + format, *args)


def start_identity_server(config: BridgeConfig) -> None:
    if config.identity_port <= 0:
        logging.info("Local identity endpoint disabled.")
        return

    handler = type("ConfiguredLocalIdentityHandler", (LocalIdentityHandler,), {"config": config})
    try:
        server = ThreadingHTTPServer((config.identity_host, config.identity_port), handler)
    except OSError as exc:
        logging.warning("Local identity endpoint unavailable on %s:%s: %s", config.identity_host, config.identity_port, exc)
        return

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.info(
        "Local identity endpoint listening at http://%s:%s/identity for device=%s workstation=%s",
        config.identity_host,
        config.identity_port,
        config.device_id,
        config.workstation_id,
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def list_available_ports() -> list[Any]:
    return list(serial.tools.list_ports.comports())


def is_candidate_port(port: Any) -> bool:
    if port.vid == CH340_VID and port.pid == CH340_PID:
        return True

    device = str(getattr(port, "device", "") or "")
    metadata = " ".join(
        str(value or "").lower()
        for value in (
            getattr(port, "description", ""),
            getattr(port, "manufacturer", ""),
            getattr(port, "product", ""),
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
    ports = list_available_ports()
    preferred = [port for port in ports if port.vid == CH340_VID and port.pid == CH340_PID]
    if preferred:
        return preferred[0].device

    candidates = [port for port in ports if is_candidate_port(port)]
    return candidates[0].device if candidates else None


def describe_available_ports() -> str:
    ports = list_available_ports()
    if not ports:
        return "none detected"

    return ", ".join(
        f"{port.device} ({port.description or 'no description'}, "
        f"VID={hex(port.vid) if port.vid else '-'}, PID={hex(port.pid) if port.pid else '-'})"
        for port in ports
    )


def parse_weight_data(raw_line: str) -> dict[str, str | bool] | None:
    line = raw_line.strip()
    if not line:
        return None

    upper = line.upper()
    stable = ("ST" in upper or "GS" in upper) or ("US" not in upper and "UNSTABLE" not in upper)
    match = re.search(r"([+-]?\s*\d+\.?\d*)\s*(KG|LBS|LB|OZ|T\b|G\b)", upper)
    if match:
        weight_str = match.group(1).replace(" ", "")
        unit_map = {"KG": "kg", "LBS": "lb", "LB": "lb", "OZ": "oz", "T": "t", "G": "g"}
        try:
            return {
                "weight": f"{float(weight_str):.3f}",
                "unit": unit_map.get(match.group(2), match.group(2).lower()),
                "stable": stable,
            }
        except ValueError:
            return None

    numeric_match = re.search(r"([+-]?\s*\d+\.?\d*)", line)
    if not numeric_match:
        return None

    try:
        return {
            "weight": f"{float(numeric_match.group(1).replace(' ', '')):.3f}",
            "unit": "kg",
            "stable": stable,
        }
    except ValueError:
        return None


def push_state(session: requests.Session, config: BridgeConfig, state: BridgeState) -> None:
    payload = {
        "device_id": config.device_id,
        "workstation_id": config.workstation_id,
        "weight": state.weight,
        "unit": state.unit,
        "status": state.status,
        "raw_value": state.raw_value,
        "captured_at": (state.captured_at or now_utc()).isoformat(),
        "source": "local_bridge",
        "error": state.error or None,
        "detected_port": state.detected_port,
    }
    response = session.post(
        f"{config.server_url}/api/scale/bridge/readings/",
        json=payload,
        timeout=10,
        headers={"X-Bridge-Api-Key": config.bridge_api_key},
    )
    response.raise_for_status()
    logging.info(
        "Push success: status=%s weight=%s %s device=%s workstation=%s response=%s",
        state.status,
        state.weight,
        state.unit,
        config.device_id,
        config.workstation_id,
        response.text.strip(),
    )


def build_disconnected_state(*, status: str, error: str, detected_port: str | None) -> BridgeState:
    return BridgeState(
        status=status,
        weight="0.000",
        unit="kg",
        raw_value="",
        error=error,
        detected_port=detected_port,
        captured_at=now_utc(),
    )


def open_serial_connection(config: BridgeConfig) -> tuple[serial.Serial | None, str | None, BridgeState]:
    port_name = config.serial_port if config.serial_port != "AUTO" else find_auto_port()
    if not port_name:
        return None, None, build_disconnected_state(
            status="no_serial_port",
            error="No serial port detected on this workstation.",
            detected_port=None,
        )

    logging.info("Opening serial port %s at %d baud", port_name, config.serial_baud_rate)
    try:
        serial_conn = serial.Serial(
            port=port_name,
            baudrate=config.serial_baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1,
        )
    except serial.SerialException as exc:
        return None, port_name, build_disconnected_state(
            status="error",
            error=str(exc),
            detected_port=port_name,
        )

    return serial_conn, port_name, BridgeState(
        status="connected",
        weight="0.000",
        unit="kg",
        raw_value="",
        error="",
        detected_port=port_name,
        captured_at=now_utc(),
    )


def main() -> None:
    setup_logging()
    config = load_config()
    start_identity_server(config)
    session = requests.Session()
    serial_conn: serial.Serial | None = None
    active_port: str | None = None
    state = build_disconnected_state(status="disconnected", error="Bridge starting.", detected_port=None)
    last_push_at = 0.0
    last_valid_read_at = 0.0

    logging.info(
        "Scale bridge started: os=%s platform=%s device=%s workstation=%s server=%s port=%s baud_rate=%s visible_ports=%s",
        platform.platform(),
        sys.platform,
        config.device_id,
        config.workstation_id,
        config.server_url,
        config.serial_port,
        config.serial_baud_rate,
        describe_available_ports(),
    )

    while True:
        try:
            if serial_conn is None or not serial_conn.is_open:
                serial_conn, active_port, state = open_serial_connection(config)
                last_push_at = 0.0
                if serial_conn is None:
                    logging.warning("Serial open failed: %s", state.error)
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    logging.info("Connected to serial port %s", active_port)

            if serial_conn is not None and serial_conn.is_open:
                raw_bytes = serial_conn.readline()
                if raw_bytes:
                    raw_line = raw_bytes.decode("utf-8", errors="replace").strip()
                    if raw_line:
                        logging.info("Raw value: %s", raw_line)
                        parsed = parse_weight_data(raw_line)
                        if parsed is None:
                            state = BridgeState(
                                status="invalid_reading",
                                weight="0.000",
                                unit="kg",
                                raw_value=raw_line,
                                error="Unable to parse weight from serial data.",
                                detected_port=active_port,
                                captured_at=now_utc(),
                            )
                        else:
                            state = BridgeState(
                                status="stable" if parsed["stable"] else "unstable",
                                weight=parsed["weight"],
                                unit=parsed["unit"],
                                raw_value=raw_line,
                                error="",
                                detected_port=active_port,
                                captured_at=now_utc(),
                            )
                            last_valid_read_at = time.monotonic()
                            logging.info(
                                "Parsed weight: %s %s on %s",
                                state.weight,
                                state.unit,
                                active_port,
                            )

                if serial_conn is not None and serial_conn.is_open and last_valid_read_at:
                    if time.monotonic() - last_valid_read_at > config.stale_after_seconds:
                        state = BridgeState(
                            status="disconnected",
                            weight="0.000",
                            unit="kg",
                            raw_value=state.raw_value,
                            error="No valid weight received within stale threshold.",
                            detected_port=active_port,
                            captured_at=now_utc(),
                        )

            if time.monotonic() - last_push_at >= config.push_interval_ms / 1000:
                push_state(session, config, state)
                last_push_at = time.monotonic()

            time.sleep(0.1)
        except serial.SerialException as exc:
            logging.warning("Serial exception on %s: %s", active_port, exc)
            state = build_disconnected_state(status="disconnected", error=str(exc), detected_port=active_port)
            if serial_conn is not None and serial_conn.is_open:
                serial_conn.close()
            serial_conn = None
            time.sleep(RETRY_DELAY_SECONDS)
        except requests.RequestException as exc:
            logging.warning("Push failed: %s", exc)
            time.sleep(RETRY_DELAY_SECONDS)
        except KeyboardInterrupt:
            logging.info("Scale bridge stopped by user.")
            if serial_conn is not None and serial_conn.is_open:
                serial_conn.close()
            return
        except Exception as exc:  # pragma: no cover - last-resort protection
            logging.exception("Unexpected bridge error: %s", exc)
            state = build_disconnected_state(status="error", error=str(exc), detected_port=active_port)
            if serial_conn is not None and serial_conn.is_open:
                serial_conn.close()
            serial_conn = None
            time.sleep(RETRY_DELAY_SECONDS)


if __name__ == "__main__":
    main()
