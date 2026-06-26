from django.db import models
from django.utils import timezone


class ScaleBridgeReading(models.Model):
    class Status(models.TextChoices):
        CONNECTED = "connected", "Connected"
        STABLE = "stable", "Stable"
        UNSTABLE = "unstable", "Unstable"
        DISCONNECTED = "disconnected", "Disconnected"
        ERROR = "error", "Error"
        NO_SERIAL_PORT = "no_serial_port", "No Serial Port"
        INVALID_READING = "invalid_reading", "Invalid Reading"
        BRIDGE_NOT_REPORTING = "bridge_not_reporting", "Bridge Not Reporting"

    device_id = models.CharField(max_length=100, db_index=True)
    workstation_id = models.CharField(max_length=100, db_index=True)
    weight = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    unit = models.CharField(max_length=16, default="kg")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DISCONNECTED)
    raw_value = models.TextField(blank=True)
    source = models.CharField(max_length=32, default="local_bridge")
    detected_port = models.CharField(max_length=100, blank=True)
    error = models.TextField(blank=True)
    captured_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen_at", "device_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["device_id", "workstation_id"],
                name="scale_bridge_device_workstation_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["device_id", "workstation_id"], name="scale_bridge_device_ws_idx"),
            models.Index(fields=["workstation_id", "last_seen_at"], name="scale_bridge_ws_seen_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.device_id} @ {self.workstation_id}"
