import json
from types import SimpleNamespace
from datetime import timedelta
from unittest import TestCase, skipIf
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase as DjangoTestCase, override_settings
from django.utils import timezone

from .models import ScaleBridgeReading

try:
    from . import serial_reader
except ImportError:
    serial_reader = None


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


@skipIf(serial_reader is None, "apps.scale.serial_reader is not present in this checkout.")
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


@skipIf(serial_reader is None, "apps.scale.serial_reader is not present in this checkout.")
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


@skipIf(serial_reader is None, "apps.scale.serial_reader is not present in this checkout.")
class LatestWeightServerSerialEndpointTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("apps.scale.views.serial_reader.get_latest_weight")
    def test_latest_weight_without_ids_uses_server_serial_reader(self, get_latest_weight):
        get_latest_weight.return_value = {
            "status": "stable",
            "weight": "12.345",
            "unit": "kg",
            "source": "server_serial",
        }

        from .views import LatestWeightView

        response = LatestWeightView.as_view()(self.factory.get("/api/scale/weight/latest/"))
        payload = json.loads(response.content.decode("utf-8"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "stable")
        self.assertEqual(payload["source"], "server_serial")
        get_latest_weight.assert_called_once_with()


@skipIf(serial_reader is None, "apps.scale.serial_reader is not present in this checkout.")
@override_settings(SCALE_ENABLED=True, SCALE_STALE_AFTER_SECONDS=5)
class ServerSerialStalePayloadTests(SimpleTestCase):
    def tearDown(self):
        from apps.weighscale import serial_manager

        with serial_manager._lock:
            serial_manager._latest_payload = None

    @patch("apps.scale.serial_reader._connect_if_needed", return_value=(True, None, "/dev/ttyUSB0"))
    def test_stale_server_serial_reading_becomes_disconnected(self, _connect_if_needed):
        from apps.weighscale import serial_manager

        stale_seen_at = (timezone.now() - timedelta(seconds=30)).isoformat()
        with serial_manager._lock:
            serial_manager._latest_payload = {
                "status": "stable",
                "weight": "15.250",
                "unit": "kg",
                "stable": True,
                "timestamp": stale_seen_at,
                "captured_at": stale_seen_at,
                "last_seen_at": stale_seen_at,
                "raw_data": "ST,GS,+15.250kg",
                "detected_port": "/dev/ttyUSB0",
            }

        payload = serial_reader.get_latest_weight()

        self.assertEqual(payload["status"], "disconnected")
        self.assertEqual(payload["weight"], "15.250")
        self.assertEqual(payload["source"], "server_serial")
        self.assertEqual(payload["detected_port"], "/dev/ttyUSB0")


@override_settings(SCALE_BRIDGE_API_KEY="bridge-secret", SCALE_BRIDGE_STALE_AFTER_SECONDS=5)
class ScaleBridgeApiTests(DjangoTestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="scale-tester", password="secret123")
        self.client.force_login(self.user)
        self.auth_headers = {"HTTP_X_API_KEY": "internal-secret"}
        self.bridge_headers = {"X-Bridge-Api-Key": "bridge-secret"}
        self.primary_client_id = "production-pc-01"
        self.secondary_client_id = "production-pc-02"

    def test_bridge_ingest_rejects_missing_api_key(self):
        response = self.client.post(
            "/api/scale/bridge/readings/",
            data=(
                '{"device_id":"AD-WEIGH-01","workstation_id":"PC-01","bridge_client_id":"production-pc-01",'
                '"status":"connected","weight":12.345}'
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(ScaleBridgeReading.objects.count(), 0)

    def test_bridge_ingest_upserts_latest_reading(self):
        response = self.client.post(
            "/api/scale/bridge/readings/",
            data=(
                '{"device_id":"AD-WEIGH-01","workstation_id":"PC-01","bridge_client_id":"production-pc-01",'
                '"status":"connected","weight":12.345,"unit":"kg","raw_value":"ST,GS,+12.345kg","source":"local_bridge"}'
            ),
            content_type="application/json",
            headers=self.bridge_headers,
        )

        self.assertEqual(response.status_code, 200)
        reading = ScaleBridgeReading.objects.get(
            device_id="AD-WEIGH-01",
            workstation_id="PC-01",
            bridge_client_id=self.primary_client_id,
        )
        self.assertEqual(reading.workstation_id, "PC-01")
        self.assertEqual(reading.bridge_client_id, self.primary_client_id)
        self.assertEqual(str(reading.weight), "12.345")
        self.assertEqual(reading.status, ScaleBridgeReading.Status.CONNECTED)

    def test_bridge_ingest_accepts_stable_reading_with_weight(self):
        response = self.client.post(
            "/api/scale/bridge/readings/",
            data=(
                '{"device_id":"AD-WEIGH-01","workstation_id":"PC-01","bridge_client_id":"production-pc-01",'
                '"status":"stable","weight":12.345,"unit":"kg"}'
            ),
            content_type="application/json",
            headers=self.bridge_headers,
        )

        self.assertEqual(response.status_code, 200)
        reading = ScaleBridgeReading.objects.get(
            device_id="AD-WEIGH-01",
            workstation_id="PC-01",
            bridge_client_id=self.primary_client_id,
        )
        self.assertEqual(reading.status, ScaleBridgeReading.Status.STABLE)

    def test_bridge_ingest_rejects_unstable_reading_without_weight(self):
        response = self.client.post(
            "/api/scale/bridge/readings/",
            data=(
                '{"device_id":"AD-WEIGH-01","workstation_id":"PC-01","bridge_client_id":"production-pc-01",'
                '"status":"unstable"}'
            ),
            content_type="application/json",
            headers=self.bridge_headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ScaleBridgeReading.objects.count(), 0)

    def test_bridge_ingest_keeps_same_device_on_different_workstations_separate(self):
        first = self.client.post(
            "/api/scale/bridge/readings/",
            data=(
                '{"device_id":"SCALE-02","workstation_id":"WAREHOUSE-PC","bridge_client_id":"warehouse-pc",'
                '"status":"connected","weight":4.200}'
            ),
            content_type="application/json",
            headers=self.bridge_headers,
        )
        second = self.client.post(
            "/api/scale/bridge/readings/",
            data=(
                '{"device_id":"SCALE-02","workstation_id":"PACKING-PC","bridge_client_id":"packing-pc",'
                '"status":"connected","weight":9.500}'
            ),
            content_type="application/json",
            headers=self.bridge_headers,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(ScaleBridgeReading.objects.count(), 2)
        self.assertEqual(
            str(
                ScaleBridgeReading.objects.get(
                    device_id="SCALE-02",
                    workstation_id="WAREHOUSE-PC",
                    bridge_client_id="warehouse-pc",
                ).weight
            ),
            "4.200",
        )
        self.assertEqual(
            str(
                ScaleBridgeReading.objects.get(
                    device_id="SCALE-02",
                    workstation_id="PACKING-PC",
                    bridge_client_id="packing-pc",
                ).weight
            ),
            "9.500",
        )

    def test_bridge_ingest_keeps_same_device_and_workstation_separate_per_client(self):
        now = timezone.now()
        ScaleBridgeReading.objects.create(
            device_id="SCALE-02",
            workstation_id="PRODUCTION-PC-01",
            bridge_client_id=self.primary_client_id,
            weight="4.200",
            status=ScaleBridgeReading.Status.CONNECTED,
            captured_at=now,
            last_seen_at=now,
        )
        ScaleBridgeReading.objects.create(
            device_id="SCALE-02",
            workstation_id="PRODUCTION-PC-01",
            bridge_client_id=self.secondary_client_id,
            weight="9.500",
            status=ScaleBridgeReading.Status.CONNECTED,
            captured_at=now,
            last_seen_at=now,
        )

        response = self.client.get(
            "/api/scale/weight/latest/",
            {
                "device_id": "SCALE-02",
                "workstation_id": "PRODUCTION-PC-01",
                "bridge_client_id": self.secondary_client_id,
            },
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "connected")
        self.assertEqual(payload["device_id"], "SCALE-02")
        self.assertEqual(payload["workstation_id"], "PRODUCTION-PC-01")
        self.assertEqual(payload["bridge_client_id"], self.secondary_client_id)
        self.assertEqual(payload["weight"], "9.500")

    def test_latest_weight_requires_bridge_client_id_for_bridge_requests(self):
        response = self.client.get(
            "/api/scale/weight/latest/",
            {"device_id": "AD-WEIGH-01", "workstation_id": "PC-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "bridge_client_id is required when requesting bridge scale data.")

    def test_latest_weight_returns_bridge_payload_for_exact_client(self):
        captured_at = timezone.now()
        last_seen_at = captured_at
        ScaleBridgeReading.objects.create(
            device_id="AD-WEIGH-01",
            workstation_id="PC-01",
            bridge_client_id=self.primary_client_id,
            weight="25.450",
            unit="kg",
            status=ScaleBridgeReading.Status.CONNECTED,
            raw_value="ST,GS,+25.450kg",
            source="local_bridge",
            captured_at=captured_at,
            last_seen_at=last_seen_at,
        )

        response = self.client.get(
            "/api/scale/weight/latest/",
            {
                "device_id": "AD-WEIGH-01",
                "workstation_id": "PC-01",
                "bridge_client_id": self.primary_client_id,
            },
            **self.auth_headers,
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "connected")
        self.assertEqual(payload["device_id"], "AD-WEIGH-01")
        self.assertEqual(payload["workstation_id"], "PC-01")
        self.assertEqual(payload["bridge_client_id"], self.primary_client_id)
        self.assertEqual(payload["source"], "local_bridge")

    def test_latest_weight_returns_disconnected_when_stale_for_exact_client(self):
        captured_at = timezone.now() - timedelta(seconds=30)
        ScaleBridgeReading.objects.create(
            device_id="AD-WEIGH-01",
            workstation_id="PC-01",
            bridge_client_id=self.primary_client_id,
            weight="25.450",
            unit="kg",
            status=ScaleBridgeReading.Status.CONNECTED,
            source="local_bridge",
            captured_at=captured_at,
            last_seen_at=captured_at,
        )

        response = self.client.get(
            "/api/scale/weight/latest/",
            {
                "device_id": "AD-WEIGH-01",
                "workstation_id": "PC-01",
                "bridge_client_id": self.primary_client_id,
            },
            **self.auth_headers,
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "disconnected")
        self.assertEqual(payload["device_id"], "AD-WEIGH-01")

    def test_latest_weight_prefers_most_recent_bridge_reading_when_requested(self):
        older = timezone.now() - timedelta(seconds=2)
        newer = timezone.now()
        ScaleBridgeReading.objects.create(
            device_id="AD-WEIGH-01",
            workstation_id="PC-01",
            bridge_client_id=self.primary_client_id,
            weight="10.000",
            unit="kg",
            status=ScaleBridgeReading.Status.CONNECTED,
            source="local_bridge",
            captured_at=older,
            last_seen_at=older,
        )
        ScaleBridgeReading.objects.create(
            device_id="GL-WEIGH-02",
            workstation_id="PC-02",
            bridge_client_id=self.secondary_client_id,
            weight="12.500",
            unit="kg",
            status=ScaleBridgeReading.Status.CONNECTED,
            source="local_bridge",
            captured_at=newer,
            last_seen_at=newer,
        )

        response = self.client.get("/api/scale/weight/latest/", {"prefer_bridge": "1"}, **self.auth_headers)
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "connected")
        self.assertEqual(payload["device_id"], "GL-WEIGH-02")
        self.assertEqual(payload["workstation_id"], "PC-02")
        self.assertEqual(payload["source"], "local_bridge")

    def test_bridge_demand_endpoint_reports_active_after_ui_heartbeat(self):
        response = self.client.get(
            "/api/scale/bridge/demand/",
            HTTP_X_BRIDGE_API_KEY="bridge-secret",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["active"])

        activate_response = self.client.post(
            "/api/scale/bridge/demand/activate/",
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(activate_response.status_code, 200)

        response = self.client.get(
            "/api/scale/bridge/demand/",
            HTTP_X_BRIDGE_API_KEY="bridge-secret",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["active"])

        deactivate_response = self.client.delete(
            "/api/scale/bridge/demand/activate/",
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(deactivate_response.status_code, 200)

        response = self.client.get(
            "/api/scale/bridge/demand/",
            HTTP_X_BRIDGE_API_KEY="bridge-secret",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["active"])
