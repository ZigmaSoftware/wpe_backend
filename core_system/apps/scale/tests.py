from types import SimpleNamespace
from datetime import timedelta
from unittest import TestCase
from unittest.mock import patch

from django.test import TestCase as DjangoTestCase, override_settings
from django.utils import timezone

from .models import ScaleBridgeReading
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
        self.assertEqual(payload["source"], "server_serial")


@override_settings(SCALE_BRIDGE_API_KEY="bridge-secret", SCALE_BRIDGE_STALE_AFTER_SECONDS=5)
class ScaleBridgeApiTests(DjangoTestCase):
    def test_bridge_ingest_rejects_missing_api_key(self):
        response = self.client.post(
            "/api/scale/bridge/readings/",
            data='{"device_id":"AD-WEIGH-01","workstation_id":"PC-01","status":"connected","weight":12.345}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(ScaleBridgeReading.objects.count(), 0)

    def test_bridge_ingest_upserts_latest_reading(self):
        response = self.client.post(
            "/api/scale/bridge/readings/",
            data='{"device_id":"AD-WEIGH-01","workstation_id":"PC-01","status":"connected","weight":12.345,"unit":"kg","raw_value":"ST,GS,+12.345kg","source":"local_bridge"}',
            content_type="application/json",
            headers={"X-Bridge-Api-Key": "bridge-secret"},
        )

        self.assertEqual(response.status_code, 200)
        reading = ScaleBridgeReading.objects.get(device_id="AD-WEIGH-01")
        self.assertEqual(reading.workstation_id, "PC-01")
        self.assertEqual(str(reading.weight), "12.345")
        self.assertEqual(reading.status, ScaleBridgeReading.Status.CONNECTED)

    def test_latest_weight_returns_bridge_payload_for_selected_device(self):
        captured_at = timezone.now()
        last_seen_at = captured_at
        ScaleBridgeReading.objects.create(
            device_id="AD-WEIGH-01",
            workstation_id="PC-01",
            weight="25.450",
            unit="kg",
            status=ScaleBridgeReading.Status.CONNECTED,
            raw_value="ST,GS,+25.450kg",
            source="local_bridge",
            captured_at=captured_at,
            last_seen_at=last_seen_at,
        )

        response = self.client.get("/api/scale/weight/latest/", {"device_id": "AD-WEIGH-01"})
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "connected")
        self.assertEqual(payload["device_id"], "AD-WEIGH-01")
        self.assertEqual(payload["workstation_id"], "PC-01")
        self.assertEqual(payload["source"], "local_bridge")

    def test_latest_weight_reports_bridge_not_reporting_when_stale(self):
        captured_at = timezone.now() - timedelta(seconds=30)
        ScaleBridgeReading.objects.create(
            device_id="AD-WEIGH-01",
            workstation_id="PC-01",
            weight="25.450",
            unit="kg",
            status=ScaleBridgeReading.Status.CONNECTED,
            source="local_bridge",
            captured_at=captured_at,
            last_seen_at=captured_at,
        )

        response = self.client.get("/api/scale/weight/latest/", {"device_id": "AD-WEIGH-01"})
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "bridge_not_reporting")
        self.assertEqual(payload["device_id"], "AD-WEIGH-01")
