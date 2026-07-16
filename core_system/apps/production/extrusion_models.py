"""Models for the Extrusion Production, Packing, Weight Verification, Sticker
Generation and Scrap KPI module (FRD: Extrusion_Scrap_Packing_KPI_FRD_V1_0).

This module is additive to `apps.production` — it introduces new tables only
and does not alter any existing model. It is wired into the app by a single
import line appended to the bottom of `models.py`.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from .models import ProductionCodeTrackedModel, ZERO_DECIMAL, build_prefixed_running_number


ZERO = Decimal("0.000")


class ExtrusionProfileConfig(models.Model):
    """Extrusion-specific weight/tolerance configuration for a profile.

    Kept separate from `ProfileCreationMaster` so the existing profile master
    is never modified by this module.
    """

    class ToleranceType(models.TextChoices):
        FIXED = "FIXED", "Fixed Weight"
        PERCENTAGE = "PERCENTAGE", "Percentage"

    profile = models.OneToOneField(
        "production.ProfileCreationMaster",
        on_delete=models.CASCADE,
        related_name="extrusion_config",
    )
    section_weight_per_meter = models.DecimalField(
        max_digits=12, decimal_places=3, default=ZERO, validators=[MinValueValidator(Decimal("0"))]
    )
    standard_length_per_piece = models.DecimalField(
        max_digits=12, decimal_places=3, default=ZERO, validators=[MinValueValidator(Decimal("0"))]
    )
    default_pieces_per_packet = models.PositiveIntegerField(default=1)
    default_tare_weight = models.DecimalField(
        max_digits=10, decimal_places=3, default=ZERO, validators=[MinValueValidator(Decimal("0"))]
    )
    tolerance_type = models.CharField(max_length=16, choices=ToleranceType.choices, default=ToleranceType.FIXED)
    tolerance_value = models.DecimalField(
        max_digits=10, decimal_places=3, default=ZERO, validators=[MinValueValidator(Decimal("0"))]
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Extrusion Profile Config"
        verbose_name_plural = "Extrusion Profile Configs"

    def __str__(self) -> str:
        return f"Extrusion config — {self.profile.code}"

    def compute_tolerance_amount(self, expected_gross_weight: Decimal) -> Decimal:
        if self.tolerance_type == self.ToleranceType.PERCENTAGE:
            return (Decimal(expected_gross_weight) * self.tolerance_value / Decimal("100")).quantize(Decimal("0.001"))
        return self.tolerance_value


class ExtrusionWorkOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        RELEASED = "RELEASED", "Released"
        IN_PRODUCTION = "IN_PRODUCTION", "In Production"
        PACKING_IN_PROGRESS = "PACKING_IN_PROGRESS", "Packing In Progress"
        QC_PENDING = "QC_PENDING", "QC Pending"
        COMPLETED = "COMPLETED", "Completed"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    # statuses beyond which critical fields (profile/line/packing material/tare/section weight)
    # may no longer be edited, per FRD 6.2 "Prevent editing of critical fields after
    # production, packet, weighing or sticker transactions exist."
    LOCKED_STATUSES = (
        Status.IN_PRODUCTION,
        Status.PACKING_IN_PROGRESS,
        Status.QC_PENDING,
        Status.COMPLETED,
        Status.CLOSED,
    )

    work_order_no = models.CharField(max_length=30, unique=True, blank=True, db_index=True)
    profile = models.ForeignKey(
        "production.ProfileCreationMaster", on_delete=models.PROTECT, related_name="extrusion_work_orders"
    )
    extrusion_line = models.ForeignKey(
        "production.ProductionLineMaster", on_delete=models.PROTECT, related_name="extrusion_work_orders"
    )
    production_date = models.DateField()
    shift = models.CharField(max_length=50, blank=True, default="Shift 1 (6:00 am - 2:00 pm)")
    planned_pieces = models.PositiveIntegerField(default=0)
    planned_meters = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO)
    packing_material = models.ForeignKey(
        "production.PackingMaterialMaster", on_delete=models.PROTECT, related_name="extrusion_work_orders"
    )
    expected_tare_weight = models.DecimalField(
        max_digits=10, decimal_places=3, default=ZERO, validators=[MinValueValidator(Decimal("0"))]
    )
    expected_section_weight_per_meter = models.DecimalField(
        max_digits=12, decimal_places=3, default=ZERO, validators=[MinValueValidator(Decimal("0"))]
    )
    tolerance_type = models.CharField(
        max_length=16, choices=ExtrusionProfileConfig.ToleranceType.choices,
        default=ExtrusionProfileConfig.ToleranceType.FIXED,
    )
    tolerance_value = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    released_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-production_date", "-created_at"]
        indexes = [
            models.Index(fields=["status", "production_date"], name="ext_wo_status_date_idx"),
            models.Index(fields=["extrusion_line", "status"], name="ext_wo_line_status_idx"),
        ]
        verbose_name = "Extrusion Work Order"
        verbose_name_plural = "Extrusion Work Orders"

    def __str__(self) -> str:
        return self.work_order_no or f"Extrusion WO #{self.pk}"

    @property
    def is_locked_for_critical_edits(self) -> bool:
        return self.status in self.LOCKED_STATUSES or self.packets.exists()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.work_order_no:
                self.work_order_no = build_prefixed_running_number(
                    type(self), field_name="work_order_no", prefix="EWO", width=5, instance=self
                )
            super().save(*args, **kwargs)


class ExtrusionWorkOrderConsumable(models.Model):
    work_order = models.ForeignKey(ExtrusionWorkOrder, on_delete=models.CASCADE, related_name="consumables")
    item = models.ForeignKey("wpe_masters.ItemMaster", on_delete=models.PROTECT, related_name="extrusion_wo_consumables")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO, validators=[MinValueValidator(Decimal("0"))])
    uom = models.CharField(max_length=20, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["work_order", "item"], name="ext_wo_consumable_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.work_order.work_order_no} — {self.item.item_name}"


class ExtrusionInspection(models.Model):
    class Result(models.TextChoices):
        PASS = "PASS", "Pass"
        FAIL = "FAIL", "Fail"
        NA = "NA", "Not Applicable"

    class OverallResult(models.TextChoices):
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"

    class RejectionDecision(models.TextChoices):
        NONE = "NONE", "—"
        REWORK = "REWORK", "Rework"
        HOLD = "HOLD", "Hold"
        SCRAP = "SCRAP", "Scrap"

    MANDATORY_FIELDS = (
        "straightness_result",
        "flatness_result",
        "section_weight_result",
        "length_result",
        "visual_result",
    )

    work_order = models.ForeignKey(ExtrusionWorkOrder, on_delete=models.PROTECT, related_name="inspections")
    batch_reference = models.CharField(max_length=100, blank=True)
    inspected_pieces = models.PositiveIntegerField(default=0)

    straightness_result = models.CharField(max_length=4, choices=Result.choices, default=Result.NA)
    flatness_result = models.CharField(max_length=4, choices=Result.choices, default=Result.NA)
    section_weight_result = models.CharField(max_length=4, choices=Result.choices, default=Result.NA)
    length_result = models.CharField(max_length=4, choices=Result.choices, default=Result.NA)
    visual_result = models.CharField(max_length=4, choices=Result.choices, default=Result.NA)
    dimensional_result = models.CharField(max_length=4, choices=Result.choices, default=Result.NA)

    overall_result = models.CharField(max_length=10, choices=OverallResult.choices, blank=True, db_index=True)
    rejection_decision = models.CharField(
        max_length=10, choices=RejectionDecision.choices, default=RejectionDecision.NONE
    )
    rejection_reason = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    inspected_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-inspected_at"]
        indexes = [
            models.Index(fields=["work_order", "overall_result"], name="ext_insp_wo_result_idx"),
        ]
        verbose_name = "Extrusion Inspection"
        verbose_name_plural = "Extrusion Inspections"

    def __str__(self) -> str:
        return f"{self.work_order.work_order_no} — {self.get_overall_result_display() or 'Pending'}"

    def compute_overall_result(self) -> None:
        relevant_results = [getattr(self, field) for field in self.MANDATORY_FIELDS]
        has_failure = any(value == self.Result.FAIL for value in relevant_results if value != self.Result.NA)
        self.overall_result = self.OverallResult.REJECTED if has_failure else self.OverallResult.ACCEPTED

    def clean(self):
        super().clean()
        self.compute_overall_result()
        if self.overall_result == self.OverallResult.REJECTED:
            if self.rejection_decision == self.RejectionDecision.NONE:
                raise ValidationError({"rejection_decision": "A rejection decision (Rework/Hold/Scrap) is required."})
            if not str(self.rejection_reason or "").strip():
                raise ValidationError({"rejection_reason": "A reason is mandatory for rejected inspections."})

    def save(self, *args, **kwargs):
        self.compute_overall_result()
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_accepted(self) -> bool:
        return self.overall_result == self.OverallResult.ACCEPTED


def _build_packet_no_for_work_order(work_order: ExtrusionWorkOrder, *, exclude_pk: int | None = None) -> str:
    prefix = f"{work_order.work_order_no}-P"
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    queryset = Packet.objects.select_for_update().filter(work_order=work_order)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    highest = 0
    for packet_no in queryset.values_list("packet_no", flat=True):
        match = pattern.match(str(packet_no or "").strip().upper())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{prefix}{highest + 1:03d}"


class Packet(models.Model):
    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        AWAITING_WEIGHT = "AWAITING_WEIGHT", "Awaiting Weight"
        WEIGHT_ACCEPTED = "WEIGHT_ACCEPTED", "Weight Accepted"
        WEIGHT_REJECTED = "WEIGHT_REJECTED", "Weight Rejected"
        STICKER_GENERATED = "STICKER_GENERATED", "Sticker Generated"
        STICKER_SCANNED = "STICKER_SCANNED", "Sticker Scanned"
        QC_APPROVED = "QC_APPROVED", "QC Approved"
        MOVED_TO_WAREHOUSE = "MOVED_TO_WAREHOUSE", "Moved to Warehouse"
        SCRAPPED = "SCRAPPED", "Scrapped"
        CANCELLED = "CANCELLED", "Cancelled"

    work_order = models.ForeignKey(ExtrusionWorkOrder, on_delete=models.PROTECT, related_name="packets")
    inspection = models.ForeignKey(ExtrusionInspection, on_delete=models.PROTECT, related_name="packets")
    packet_no = models.CharField(max_length=40, unique=True, blank=True, db_index=True)

    pieces = models.PositiveIntegerField()
    length_per_piece = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0"))])
    total_meters = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO)
    packing_material = models.ForeignKey(
        "production.PackingMaterialMaster", on_delete=models.PROTECT, related_name="extrusion_packets"
    )

    # Historical snapshot — captured at creation time so later master/config
    # changes never alter an already-created packet's calculations (FRD 6.1).
    tare_weight = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    section_weight_per_meter = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO)
    tolerance_type = models.CharField(
        max_length=16, choices=ExtrusionProfileConfig.ToleranceType.choices,
        default=ExtrusionProfileConfig.ToleranceType.FIXED,
    )
    tolerance_value = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)

    expected_net_weight = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO)
    expected_gross_weight = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO)
    tolerance_amount = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    min_permissible_weight = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO)
    max_permissible_weight = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO)

    actual_gross_weight = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    weight_deviation = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    deviation_percentage = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)

    status = models.CharField(max_length=24, choices=Status.choices, default=Status.CREATED, db_index=True)

    qc_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    qc_approved_at = models.DateTimeField(null=True, blank=True)
    qc_approval_remarks = models.TextField(blank=True)

    warehouse = models.ForeignKey(
        "wpe_masters.WarehouseMaster", null=True, blank=True, on_delete=models.SET_NULL, related_name="extrusion_packets"
    )
    warehouse_received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    warehouse_received_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["work_order", "status"], name="ext_packet_wo_status_idx"),
        ]
        verbose_name = "Extrusion Packet"
        verbose_name_plural = "Extrusion Packets"

    def __str__(self) -> str:
        return self.packet_no or f"Packet #{self.pk}"

    def compute_expected_values(self) -> None:
        self.total_meters = (Decimal(self.pieces) * self.length_per_piece).quantize(Decimal("0.001"))
        self.expected_net_weight = (self.section_weight_per_meter * self.total_meters).quantize(Decimal("0.001"))
        self.expected_gross_weight = (self.expected_net_weight + self.tare_weight).quantize(Decimal("0.001"))
        if self.tolerance_type == ExtrusionProfileConfig.ToleranceType.PERCENTAGE:
            self.tolerance_amount = (
                self.expected_gross_weight * self.tolerance_value / Decimal("100")
            ).quantize(Decimal("0.001"))
        else:
            self.tolerance_amount = self.tolerance_value
        self.min_permissible_weight = (self.expected_gross_weight - self.tolerance_amount).quantize(Decimal("0.001"))
        self.max_permissible_weight = (self.expected_gross_weight + self.tolerance_amount).quantize(Decimal("0.001"))

    def evaluate_weight(self, actual_gross_weight: Decimal) -> str:
        actual = Decimal(actual_gross_weight)
        if actual < self.min_permissible_weight:
            return PacketWeightAttempt.Result.UNDERWEIGHT
        if actual > self.max_permissible_weight:
            return PacketWeightAttempt.Result.OVERWEIGHT
        return PacketWeightAttempt.Result.ACCEPTED

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.packet_no:
                self.packet_no = _build_packet_no_for_work_order(self.work_order, exclude_pk=self.pk)
            super().save(*args, **kwargs)


class PacketWeightAttempt(models.Model):
    class Result(models.TextChoices):
        ACCEPTED = "ACCEPTED", "Accepted"
        UNDERWEIGHT = "UNDERWEIGHT", "Underweight"
        OVERWEIGHT = "OVERWEIGHT", "Overweight"

    class Source(models.TextChoices):
        SCALE = "SCALE", "Scale"
        MANUAL = "MANUAL", "Manual"

    packet = models.ForeignKey(Packet, on_delete=models.CASCADE, related_name="weight_attempts")
    attempt_no = models.PositiveIntegerField()
    actual_gross_weight = models.DecimalField(max_digits=14, decimal_places=3)
    result = models.CharField(max_length=16, choices=Result.choices)
    weight_deviation = models.DecimalField(max_digits=14, decimal_places=3)
    deviation_percentage = models.DecimalField(max_digits=7, decimal_places=3)

    source = models.CharField(max_length=16, choices=Source.choices, default=Source.SCALE)
    device_id = models.CharField(max_length=100, blank=True)
    workstation_id = models.CharField(max_length=100, blank=True)
    bridge_client_id = models.CharField(max_length=128, blank=True)

    is_override = models.BooleanField(default=False)
    override_reason = models.TextField(blank=True)
    override_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    weighed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    weighed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["packet", "attempt_no"]
        constraints = [
            models.UniqueConstraint(fields=["packet", "attempt_no"], name="ext_weight_attempt_unique"),
        ]
        verbose_name = "Packet Weight Attempt"
        verbose_name_plural = "Packet Weight Attempts"

    def __str__(self) -> str:
        return f"{self.packet.packet_no} — attempt {self.attempt_no} ({self.result})"


class PacketSticker(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CANCELLED = "CANCELLED", "Cancelled"
        SUPERSEDED = "SUPERSEDED", "Superseded"
        SCRAPPED = "SCRAPPED", "Scrapped"

    packet = models.OneToOneField(Packet, on_delete=models.CASCADE, related_name="sticker")
    sticker_no = models.CharField(max_length=30, unique=True, blank=True, db_index=True)
    qr_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    reprint_count = models.PositiveIntegerField(default=0)
    last_reprint_reason = models.TextField(blank=True)
    last_reprint_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    last_reprint_at = models.DateTimeField(null=True, blank=True)

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    generated_at = models.DateTimeField(default=timezone.now)

    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    scanned_at = models.DateTimeField(null=True, blank=True)

    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-generated_at"]
        verbose_name = "Packet Sticker"
        verbose_name_plural = "Packet Stickers"

    def __str__(self) -> str:
        return self.sticker_no or f"Sticker #{self.pk}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.sticker_no:
                self.sticker_no = build_prefixed_running_number(
                    type(self), field_name="sticker_no", prefix="STK", width=6, instance=self
                )
            super().save(*args, **kwargs)


class StickerScanLog(models.Model):
    class Result(models.TextChoices):
        OK = "OK", "OK"
        ALREADY_USED = "ALREADY_USED", "Already Used"
        CANCELLED = "CANCELLED", "Cancelled"
        MISMATCH = "MISMATCH", "Mismatch"

    sticker = models.ForeignKey(PacketSticker, on_delete=models.CASCADE, related_name="scan_logs")
    packet = models.ForeignKey(Packet, on_delete=models.CASCADE, related_name="scan_logs")
    result = models.CharField(max_length=16, choices=Result.choices)
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    scanned_at = models.DateTimeField(default=timezone.now)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-scanned_at"]
        verbose_name = "Sticker Scan Log"
        verbose_name_plural = "Sticker Scan Logs"

    def __str__(self) -> str:
        return f"{self.sticker.sticker_no} — {self.result}"


class ScrapCategory(ProductionCodeTrackedModel):
    code_prefix = "SCRC"
    code_width = 2

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "Scrap Category"
        verbose_name_plural = "Scrap Categories"


class ScrapReason(ProductionCodeTrackedModel):
    code_prefix = "SCRR"
    code_width = 3

    category = models.ForeignKey(ScrapCategory, on_delete=models.PROTECT, related_name="reasons")

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "Scrap Reason"
        verbose_name_plural = "Scrap Reasons"


class ScrapTransaction(models.Model):
    class SourceStage(models.TextChoices):
        QC_INSPECTION = "QC_INSPECTION", "QC Inspection Scrap"
        PACKING = "PACKING", "Packing Scrap"
        WEIGHT_VERIFICATION = "WEIGHT_VERIFICATION", "Weight Verification Scrap"
        SHIFT_END_QC = "SHIFT_END_QC", "Shift-End QC Scrap"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        CONFIRMED = "CONFIRMED", "Confirmed"
        APPROVED = "APPROVED", "Approved"
        CLOSED = "CLOSED", "Closed"
        REVERSED = "REVERSED", "Reversed"

    ACTIVE_STATUSES = (Status.DRAFT, Status.CONFIRMED, Status.APPROVED, Status.CLOSED)

    source_stage = models.CharField(max_length=24, choices=SourceStage.choices, db_index=True)
    work_order = models.ForeignKey(ExtrusionWorkOrder, on_delete=models.PROTECT, related_name="scrap_transactions")
    profile = models.ForeignKey(
        "production.ProfileCreationMaster", on_delete=models.PROTECT, related_name="extrusion_scrap_transactions"
    )
    inspection = models.ForeignKey(
        ExtrusionInspection, null=True, blank=True, on_delete=models.SET_NULL, related_name="scrap_transactions"
    )
    packet = models.ForeignKey(
        Packet, null=True, blank=True, on_delete=models.SET_NULL, related_name="scrap_transactions"
    )
    production_date = models.DateField()
    shift = models.CharField(max_length=50, blank=True)

    scrap_category = models.ForeignKey(ScrapCategory, on_delete=models.PROTECT, related_name="scrap_transactions")
    scrap_reason = models.ForeignKey(ScrapReason, on_delete=models.PROTECT, related_name="scrap_transactions")
    actual_scrap_weight = models.DecimalField(
        max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    remarks = models.TextField(blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["work_order", "status"], name="ext_scrap_wo_status_idx"),
            models.Index(fields=["production_date", "shift"], name="ext_scrap_date_shift_idx"),
            models.Index(fields=["scrap_category", "scrap_reason"], name="ext_scrap_cat_reason_idx"),
        ]
        verbose_name = "Extrusion Scrap Transaction"
        verbose_name_plural = "Extrusion Scrap Transactions"

    def __str__(self) -> str:
        return f"{self.work_order.work_order_no} — {self.actual_scrap_weight}kg ({self.get_source_stage_display()})"

    def clean(self):
        super().clean()
        if self.source_stage == self.SourceStage.QC_INSPECTION and not self.inspection_id:
            raise ValidationError({"inspection": "QC Inspection scrap must reference an inspection."})
        if self.source_stage != self.SourceStage.QC_INSPECTION and not self.packet_id:
            raise ValidationError({"packet": "Packing/Weight Verification/Shift-End QC scrap must reference a packet."})


class ExtrusionAuditLog(models.Model):
    entity_type = models.CharField(max_length=40, db_index=True)
    entity_id = models.CharField(max_length=40, db_index=True)
    action = models.CharField(max_length=40)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reason = models.TextField(blank=True)
    remarks = models.TextField(blank=True)
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=32, blank=True, default="web")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"], name="ext_audit_entity_idx"),
        ]
        verbose_name = "Extrusion Audit Log"
        verbose_name_plural = "Extrusion Audit Logs"

    def __str__(self) -> str:
        return f"{self.entity_type}#{self.entity_id} — {self.action}"
