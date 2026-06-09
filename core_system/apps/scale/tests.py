from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from . import serial_reader


def make_port(
    device: str,
    *,
    description: str = "",
    vid: int | None = None,
    pid: int | None = None,
    manufacturer: str = "",
    product: str = "",
    interface: str = "",
    hwid: str = "",
):
    return SimpleNamespace(
        device=device,
        description=description,
        vid=vid,
        pid=pid,
        manufacturer=manufacturer,
        product=product,
        interface=interface,
        hwid=hwid,
        serial_number="",
    )


class AutoPortSelectionTests(TestCase):
    def setUp(self):
        serial_reader._failed_ports_until.clear()
        serial_reader._last_no_port_warning_at = 0.0

    @patch("apps.scale.serial_reader.serial.tools.list_ports.comports")
    def test_prefers_ch340_port_when_available(self, comports_mock):
        comports_mock.return_value = [
            make_port("/dev/ttyUSB1", description="USB Serial"),
            make_port(
                "/dev/ttyUSB0",
                description="QinHeng Electronics CH340",
                vid=serial_reader.CH340_VID,
                pid=serial_reader.CH340_PID,
            ),
        ]

        self.assertEqual(serial_reader.find_auto_port(), "/dev/ttyUSB0")

    @patch("apps.scale.serial_reader.serial.tools.list_ports.comports")
    def test_ignores_linux_builtin_ttys_ports_in_auto_mode(self, comports_mock):
        comports_mock.return_value = [
            make_port("/dev/ttyS3", description="Standard serial port"),
        ]

        self.assertIsNone(serial_reader.find_auto_port())

    @patch("apps.scale.serial_reader.serial.tools.list_ports.comports")
    def test_skips_failed_port_during_cooldown(self, comports_mock):
        serial_reader._mark_port_failed("/dev/ttyUSB0")
        comports_mock.return_value = [
            make_port("/dev/ttyUSB0", description="USB Serial A"),
            make_port("/dev/ttyUSB1", description="USB Serial B"),
        ]

        self.assertEqual(serial_reader.find_auto_port(), "/dev/ttyUSB1")


class ScaleDisabledStateTests(TestCase):
    def test_disabled_weight_payload_is_disconnected(self):
        payload = serial_reader.get_disabled_weight()

        self.assertEqual(payload["status"], "disconnected")
        self.assertEqual(payload["weight"], "0.000")
        self.assertEqual(payload["unit"], "kg")
        self.assertEqual(payload["error"], serial_reader.SCALE_DISABLED_ERROR)
        self.assertIsNone(payload["detected_port"])
        self.assertTrue(payload["timestamp"])
