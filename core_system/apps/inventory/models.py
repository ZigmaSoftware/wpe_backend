from decimal import Decimal

from django.conf import settings
from django.db import models

ZERO = Decimal("0.000")


class ProductionInventoryTransaction(models.Model):
    class Stage(models.TextChoices):
        ADDITIVE_WORK_CENTER = "ADDITIVE_WORK_CENTER", "Additive Work Center"
        BLEND_WIP = "BLEND_WIP", "Blend WIP"
        BLENDING_WORK_CENTER = "BLENDING_WORK_CENTER", "Blending Work Center"
        BLEND_STORE = "BLEND_STORE", "Blend Store"
        GRAN_TOOL_SCAN = "GRAN_TOOL_SCAN", "Gran Tool Scan"
        GRANULATION_WIP = "GRANULATION_WIP", "Granulation WIP"
        GRANULATION_WORK_CENTER = "GRANULATION_WORK_CENTER", "Granulation Work Center"
        GRANULATION_STORE = "GRANULATION_STORE", "Granulation Store"
        CONNECTION_TO_LINE = "CONNECTION_TO_LINE", "Connection to Line"
        LINE_WORK_CENTER = "LINE_WORK_CENTER", "Line Work Center"
        DISCONNECTION_FROM_LINE = "DISCONNECTION_FROM_LINE", "Disconnection from Line"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    stage = models.CharField(max_length=30, choices=Stage.choices, db_index=True)
    movement_key = models.CharField(max_length=150, unique=True, db_index=True)
    batch_code = models.CharField(max_length=100, db_index=True)
    production_order = models.ForeignKey(
        "production.ProductionOrder",
        on_delete=models.CASCADE,
        related_name="inventory_transactions",
        null=True,
        blank=True,
    )
    production_id = models.CharField(max_length=100, blank=True, db_index=True)
    production_type = models.CharField(max_length=200, blank=True)
    source_batch = models.ForeignKey(
        "production.ProductionBatch",
        on_delete=models.SET_NULL,
        related_name="inventory_transactions",
        null=True,
        blank=True,
    )
    output_capture = models.ForeignKey(
        "production.ProductionOutputCapture",
        on_delete=models.SET_NULL,
        related_name="inventory_transactions",
        null=True,
        blank=True,
    )
    item = models.ForeignKey(
        "Items.Item",
        on_delete=models.PROTECT,
        related_name="production_inventory_transactions",
        null=True,
        blank=True,
    )
    item_code = models.CharField(max_length=100, blank=True)
    item_name = models.CharField(max_length=255, blank=True)
    inward_qty = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO)
    outward_qty = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO)
    balance_qty = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO)
    uom = models.CharField(max_length=50, blank=True)
    from_stage = models.CharField(max_length=30, blank=True)
    to_stage = models.CharField(max_length=30, blank=True)
    reference_no = models.CharField(max_length=100, blank=True, null=True)
    scan_code = models.CharField(max_length=200, blank=True, null=True)
    work_center = models.CharField(max_length=200, blank=True, null=True)
    line = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="production_inventory_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def save(self, *args, **kwargs):
        if self.item and not self.item_code:
            self.item_code = self.item.item_code
        if self.item and not self.item_name:
            self.item_name = self.item.item_name
        if self.item and not self.uom:
            self.uom = self.item.unit
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.batch_code} / {self.stage}"
