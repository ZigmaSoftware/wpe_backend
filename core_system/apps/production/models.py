import os
import re
import uuid
from decimal import Decimal
from string import ascii_uppercase

from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone


ZERO_DECIMAL = Decimal("0.000")


def build_prefixed_running_number(model_cls, *, field_name: str, prefix: str, width: int = 3, instance=None) -> str:
    queryset = model_cls.objects.select_for_update().values_list(field_name, flat=True)
    if instance and instance.pk:
        queryset = model_cls.objects.select_for_update().exclude(pk=instance.pk).values_list(field_name, flat=True)

    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    highest_number = 0
    for raw_value in queryset:
        value = str(raw_value or "").strip().upper()
        match = pattern.match(value)
        if match:
            highest_number = max(highest_number, int(match.group(1)))

    return f"{prefix}{highest_number + 1:0{width}d}"


def _alpha_suffix_to_index(value: str) -> int:
    index = 0
    for character in value:
        index = index * 26 + (ascii_uppercase.index(character) + 1)
    return index - 1


def _index_to_alpha_suffix(index: int) -> str:
    index += 1
    characters: list[str] = []
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        characters.append(ascii_uppercase[remainder])
    return "".join(reversed(characters))


def build_alpha_running_code(model_cls, *, field_name: str, prefix: str, separator: str = "-", instance=None) -> str:
    queryset = model_cls.objects.select_for_update().values_list(field_name, flat=True)
    if instance and instance.pk:
        queryset = model_cls.objects.select_for_update().exclude(pk=instance.pk).values_list(field_name, flat=True)

    pattern = re.compile(rf"^{re.escape(prefix)}{re.escape(separator)}([A-Z]+)$")
    highest_index = -1
    for raw_value in queryset:
        value = str(raw_value or "").strip().upper()
        match = pattern.match(value)
        if match:
            highest_index = max(highest_index, _alpha_suffix_to_index(match.group(1)))

    return f"{prefix}{separator}{_index_to_alpha_suffix(highest_index + 1)}"


class ProductionCodeTrackedModel(models.Model):
    code = models.CharField(max_length=50, unique=True, db_index=True, blank=True)
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    code_prefix: str = ""
    code_width: int = 3
    code_field_name = "code"

    class Meta:
        abstract = True
        ordering = ["name"]

    def clean(self):
        super().clean()
        self.name = str(self.name or "").strip()
        self.description = str(self.description or "").strip()
        current_code = getattr(self, self.code_field_name, "") or ""
        if current_code:
            setattr(self, self.code_field_name, str(current_code).strip().upper())

    def ensure_code(self):
        if getattr(self, self.code_field_name, "") or not self.code_prefix:
            return
        setattr(
            self,
            self.code_field_name,
            build_prefixed_running_number(
                type(self),
                field_name=self.code_field_name,
                prefix=self.code_prefix,
                width=self.code_width,
                instance=self,
            ),
        )

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.ensure_code()
            self.full_clean()
            return super().save(*args, **kwargs)


class ProductionOrder(models.Model):
    """Main Production Order model"""

    STATUS_CHOICES = [
        ("IN_PROGRESS", "In Progress"),
        ("PLAN_COMPLETED", "Plan Completed (Ready to Close)"),
        ("CLOSED", "Closed"),
        ("PLANNED", "Planned"),
    ]

    PRODUCTION_TYPE_CHOICES = [
        ("RECYCLING_PRODUCTION", "Recycling Production - WPE"),
        ("BLENDING_PRODUCTION", "Blending Production - WPE"),
        ("COMPOUNDING", "Compounding"),
    ]

    # Basic Information
    production_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique production order ID"
    )
    production_type = models.CharField(
        max_length=50,
        choices=PRODUCTION_TYPE_CHOICES,
        default="RECYCLING_PRODUCTION"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="IN_PROGRESS",
        db_index=True
    )
    production_for = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Production purpose, customer, or internal job reference"
    )

    # Batch Information
    batch_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True
    )
    batch_date = models.DateField(blank=True, null=True)

    # Production Details
    production_date = models.DateField()
    shift = models.CharField(
        max_length=50,
        blank=True,
        default="Shift 1 (6:00 am - 2:00 pm)",
        help_text="Production shift information"
    )

    # Planning Information
    plan_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Associated plan ID"
    )
    planned_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=ZERO_DECIMAL,
        help_text="Planned production quantity in kgs"
    )
    planned_weight = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=ZERO_DECIMAL,
        help_text="Planned weight in kgs"
    )

    # Line and Location
    line_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Production line number"
    )
    line_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Production line name (e.g., Recycling)"
    )

    # Cost Fields
    total_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=ZERO_DECIMAL,
        help_text="Total production quantity in kgs"
    )
    other_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_DECIMAL,
        help_text="Other costs (overhead, utilities, etc.)"
    )
    material_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_DECIMAL,
        help_text="Total material cost"
    )
    total_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_DECIMAL,
        help_text="Total production cost"
    )

    # Timestamps
    start_date_time = models.DateTimeField(
        default=timezone.now,
        help_text="Production start date and time"
    )
    end_date_time = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Production end date and time"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=100, blank=True, null=True)
    updated_by = models.CharField(max_length=100, blank=True, null=True)
    extra_form_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-production_date", "-created_at"]
        indexes = [
            models.Index(fields=["production_id"], name="production_id_idx"),
            models.Index(fields=["status", "production_date"], name="production_status_date_idx"),
            models.Index(fields=["production_type", "status"], name="production_type_status_idx"),
            models.Index(fields=["batch_number"], name="production_batch_idx"),
        ]
        verbose_name = "Production Order"
        verbose_name_plural = "Production Orders"

    def __str__(self):
        return f"{self.production_id} - {self.get_status_display()}"

    @property
    def cost_per_unit(self):
        """Calculate cost per unit (kg)"""
        if self.total_quantity > 0:
            return self.total_cost / self.total_quantity
        return ZERO_DECIMAL


class MaterialMovement(models.Model):
    """Track material movements in/out of production"""

    MOVEMENT_TYPE_CHOICES = [
        ("RAW_MATERIAL_IN", "Raw Material In"),
        ("OUTPUT_IN_PRODUCTION", "Output in Production"),
        ("RETURN_TO_MC", "Send Returns to MC"),
        ("OUTPUT_TO_WAREHOUSE", "Send Output to Warehouse"),
    ]

    production_order = models.ForeignKey(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="material_movements"
    )

    movement_type = models.CharField(
        max_length=50,
        choices=MOVEMENT_TYPE_CHOICES,
        db_index=True
    )

    # Material Information
    item_id = models.CharField(max_length=100, blank=True, null=True)
    item_name = models.CharField(max_length=255)
    item_code = models.CharField(max_length=100, blank=True, null=True)

    # Location Information
    source_location = models.CharField(
        max_length=255,
        help_text="Source location (Material Center, Production, etc.)"
    )
    destination_location = models.CharField(
        max_length=255,
        help_text="Destination location"
    )

    # Quantity and Unit
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        help_text="Quantity of material"
    )
    unit = models.CharField(max_length=50, default="kgs")

    # Warehouse Bin Information
    warehouse = models.CharField(max_length=100, blank=True, null=True)
    bin_number = models.CharField(max_length=100, blank=True, null=True)

    # Status and Tracking
    status = models.CharField(
        max_length=50,
        default="PENDING",
        choices=[
            ("PENDING", "Pending"),
            ("IN_TRANSIT", "In Transit"),
            ("COMPLETED", "Completed"),
        ]
    )

    # Timestamps
    movement_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-movement_date"]
        indexes = [
            models.Index(fields=["production_order", "movement_type"], name="material_movement_type_idx"),
            models.Index(fields=["movement_date"], name="material_movement_date_idx"),
        ]
        verbose_name = "Material Movement"
        verbose_name_plural = "Material Movements"

    def __str__(self):
        return f"{self.production_order.production_id} - {self.get_movement_type_display()}"


class ProductionTransaction(models.Model):
    """Detailed transaction records for production"""

    TRANSACTION_TYPE_CHOICES = [
        ("INWARD", "Inward"),
        ("OUTWARD", "Outward"),
    ]

    production_order = models.ForeignKey(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    # Transaction Details
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique transaction ID"
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        db_index=True
    )
    transaction_date = models.DateField()
    transaction_time = models.TimeField(blank=True, null=True)

    # Item Information
    item_id = models.CharField(max_length=100)
    item_number = models.CharField(max_length=100)
    item_name = models.CharField(max_length=255)
    item_code = models.CharField(max_length=100, blank=True, null=True)

    # Quantity and Weight
    quantity_in = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=ZERO_DECIMAL,
        help_text="Inward quantity"
    )
    quantity_out = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=ZERO_DECIMAL,
        help_text="Outward quantity"
    )
    unit = models.CharField(max_length=50, default="kgs")

    # Warehouse/Location
    warehouse = models.CharField(max_length=100, blank=True, null=True)
    bin_location = models.CharField(max_length=100, blank=True, null=True)

    # Tracking and References
    reference_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Reference to GRN, PO, etc."
    )
    remarks = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        indexes = [
            models.Index(fields=["transaction_id"], name="transaction_id_idx"),
            models.Index(fields=["production_order", "transaction_type"], name="transaction_type_idx"),
            models.Index(fields=["transaction_date"], name="transaction_date_idx"),
        ]
        verbose_name = "Production Transaction"
        verbose_name_plural = "Production Transactions"

    def __str__(self):
        return f"{self.transaction_id} - {self.item_name}"


class ProductionSummary(models.Model):
    """Summary and cost aggregation for production"""

    production_order = models.OneToOneField(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="summary"
    )

    # Cost Summary
    total_raw_material_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_DECIMAL,
        help_text="Total cost of raw materials"
    )
    total_other_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_DECIMAL,
        help_text="Total other costs (overhead, utilities, etc.)"
    )
    total_production_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_DECIMAL,
        help_text="Total production cost"
    )

    # Quantity Summary
    total_input_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=ZERO_DECIMAL,
        help_text="Total input quantity in kgs"
    )
    total_output_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=ZERO_DECIMAL,
        help_text="Total output quantity in kgs"
    )
    total_waste_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=ZERO_DECIMAL,
        help_text="Total waste/scrap quantity in kgs"
    )

    # Efficiency Metrics
    yield_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100.00"),
        help_text="Production yield percentage"
    )
    cost_per_unit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO_DECIMAL,
        help_text="Cost per unit of output"
    )

    # Status
    is_finalized = models.BooleanField(
        default=False,
        help_text="Whether the summary is finalized/locked"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Production Summary"
        verbose_name_plural = "Production Summaries"

    def __str__(self):
        return f"Summary for {self.production_order.production_id}"

    def calculate_totals(self):
        """Recalculate totals from related transactions and materials"""
        # This would aggregate data from transactions and material movements
        pass

    def finalize(self):
        """Finalize the summary (lock it from further edits)"""
        self.is_finalized = True
        self.save()


import hashlib


WEIGHT_MIN_GRAMS = 195
WEIGHT_MAX_GRAMS = 9205
WEIGHT_UNIT_KG_ALIASES = {"kg", "kgs", "kilogram", "kilograms"}


def normalize_weight_unit(value: str | None) -> str:
    token = str(value or "").strip().lower()
    return "kg" if token in WEIGHT_UNIT_KG_ALIASES else "g"


def convert_gram_limit_to_component_unit(limit_grams: int | Decimal, unit: str | None) -> Decimal:
    limit = Decimal(str(limit_grams))
    return limit / Decimal("1000") if normalize_weight_unit(unit) == "kg" else limit


def format_weight_value(value: Decimal | str | int | float) -> str:
    return format(Decimal(str(value)).normalize(), "f").rstrip("0").rstrip(".") or "0"


class ProductionMachine(models.Model):
    class MachineType(models.TextChoices):
        HIGH_SPEED_MIX = "HIGH_SPEED_MIX", "High Speed Mix"
        GRANULATOR = "GRANULATOR", "Granulator"
        BLENDING = "BLENDING", "Blending"
        GRANULATION = "GRANULATION", "Granulation"
        EXTRUSION = "EXTRUSION", "Extrusion"
        EXTRUDER = "EXTRUDER", "Extruder"
        MIXER = "MIXER", "Mixer"

    class CapacityUom(models.TextChoices):
        KG = "KG", "KG"
        HOUR = "HOUR", "Hour"
        KG_PER_HOUR = "KG_PER_HOUR", "KG / Hour"

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        BREAKDOWN = "BREAKDOWN", "Breakdown"

    machine_code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    machine_type = models.CharField(max_length=30, choices=MachineType.choices)
    applicable_stages = models.CharField(max_length=20, default="AD,BL")
    is_active = models.BooleanField(default=True)
    department = models.ForeignKey(
        "wpe_masters.DepartmentMaster",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="production_machines",
    )
    capacity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    capacity_uom = models.CharField(
        max_length=20,
        choices=CapacityUom.choices,
        blank=True,
    )
    serial_no = models.CharField(max_length=100, blank=True)
    manufacturer = models.CharField(max_length=150, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    location = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["machine_code"]

    def __str__(self):
        return f"{self.machine_code} — {self.name}"

    def clean(self):
        super().clean()
        self.machine_code = str(self.machine_code or "").strip().upper()
        self.name = str(self.name or "").strip()
        self.serial_no = str(self.serial_no or "").strip()
        self.manufacturer = str(self.manufacturer or "").strip()
        self.location = str(self.location or "").strip()
        self.notes = str(self.notes or "").strip()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.machine_code:
                self.machine_code = build_prefixed_running_number(
                    type(self),
                    field_name="machine_code",
                    prefix="MCH",
                    width=3,
                    instance=self,
                )
            self.full_clean()
            return super().save(*args, **kwargs)


class ProfileSizeMaster(ProductionCodeTrackedModel):
    class Uom(models.TextChoices):
        MM = "MM", "MM"
        METER = "METER", "Meter"

    code_prefix = "SIZE"
    code_width = 3

    width = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0"))])
    thickness = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0"))])
    length = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0"))])
    uom = models.CharField(max_length=16, choices=Uom.choices)

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "Profile Size"
        verbose_name_plural = "Profile Sizes"


class ColorCreationMaster(ProductionCodeTrackedModel):
    class ColorGroup(models.TextChoices):
        DARK = "DARK", "Dark"
        LIGHT = "LIGHT", "Light"

    code_prefix = "COLR"
    code_width = 3

    color_group = models.CharField(max_length=16, choices=ColorGroup.choices, blank=True)

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "Color Creation"
        verbose_name_plural = "Color Creations"


class WorkCentreCreationMaster(ProductionCodeTrackedModel):
    code_prefix = "WC"
    code_width = 3

    department = models.ForeignKey(
        "wpe_masters.DepartmentMaster",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="work_centres",
    )
    capacity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "Work Centre Creation"
        verbose_name_plural = "Work Centre Creations"


class PackingTypeMaster(ProductionCodeTrackedModel):
    class Uom(models.TextChoices):
        NOS = "NOS", "Nos"
        KG = "KG", "KG"

    code_prefix = "PACK"
    code_width = 3

    standard_pcs = models.PositiveIntegerField(default=0)
    standard_weight = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal("0"))])
    uom = models.CharField(max_length=16, choices=Uom.choices)

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "Packing Type"
        verbose_name_plural = "Packing Types"


def profile_creation_image_upload_path(instance, filename: str) -> str:
    _, ext = os.path.splitext(filename or "")
    ext = ext.lower() or ".bin"
    ref = instance.code or instance.pk or "profile"
    return f"production/profiles/{ref}/{uuid.uuid4().hex}{ext}"


class ProfileCreationMaster(ProductionCodeTrackedModel):
    class Uom(models.TextChoices):
        NOS = "NOS", "Nos"
        METER = "METER", "Meter"

    code_prefix = "PRD"
    code_width = 3

    profile_type = models.ForeignKey(
        "wpe_masters.ProductTypeCategory",
        on_delete=models.PROTECT,
        related_name="production_profiles",
    )
    profile_size = models.ForeignKey(
        "production.ProfileSizeMaster",
        on_delete=models.PROTECT,
        related_name="profiles",
    )
    color = models.ForeignKey(
        "production.ColorCreationMaster",
        on_delete=models.PROTECT,
        related_name="profiles",
    )
    length = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0"))])
    weight_per_piece = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    uom = models.CharField(max_length=16, choices=Uom.choices)
    packing_type = models.ForeignKey(
        "production.PackingTypeMaster",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="profiles",
    )
    image = models.ImageField(upload_to=profile_creation_image_upload_path, null=True, blank=True)

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "Profile Creation"
        verbose_name_plural = "Profile Creations"


class ProductionLineMaster(ProductionCodeTrackedModel):
    class CapacityUom(models.TextChoices):
        KG = "KG", "KG"
        HOUR = "HOUR", "Hour"
        KG_PER_HOUR = "KG_PER_HOUR", "KG / Hour"

    class LineStatus(models.TextChoices):
        FREE = "FREE", "Free"
        RUNNING = "RUNNING", "Running"
        MAINTENANCE = "MAINTENANCE", "Maintenance"

    code_prefix = "LINE"
    code_width = 2

    department = models.ForeignKey(
        "wpe_masters.DepartmentMaster",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="production_lines",
    )
    machine = models.ForeignKey(
        "production.ProductionMachine",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="production_lines",
    )
    line_capacity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    capacity_uom = models.CharField(max_length=20, choices=CapacityUom.choices, blank=True)
    status = models.CharField(max_length=20, choices=LineStatus.choices, default=LineStatus.FREE)

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "Production Line"
        verbose_name_plural = "Production Lines"


class BinCreationMaster(ProductionCodeTrackedModel):
    class CapacityUom(models.TextChoices):
        KG = "KG", "KG"
        NOS = "NOS", "Nos"

    class BinStatus(models.TextChoices):
        FREE = "FREE", "Free"
        OCCUPIED = "OCCUPIED", "Occupied"
        HOLD = "HOLD", "Hold"

    code_prefix = "BIN"
    code_width = 0

    department = models.ForeignKey(
        "wpe_masters.DepartmentMaster",
        on_delete=models.PROTECT,
        related_name="production_bins",
        null=True,
        blank=True,
    )
    capacity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0"))],
        null=True,
        blank=True,
    )
    capacity_uom = models.CharField(max_length=16, choices=CapacityUom.choices, blank=True, default="")
    current_status = models.CharField(max_length=16, choices=BinStatus.choices, blank=True)
    current_material = models.CharField(max_length=200, blank=True)

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "Bin Creation"
        verbose_name_plural = "Bin Creations"

    def ensure_code(self):
        if self.code:
            return
        self.code = build_alpha_running_code(type(self), field_name="code", prefix="BIN", instance=self)


class BagCreationMaster(ProductionCodeTrackedModel):
    class Uom(models.TextChoices):
        KG = "KG", "KG"

    class BagStatus(models.TextChoices):
        FREE = "FREE", "Free"
        OCCUPIED = "OCCUPIED", "Occupied"
        USED = "USED", "Used"

    code_prefix = "BAG"
    code_width = 3

    standard_weight = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0"))],
        null=True,
        blank=True,
    )
    uom = models.CharField(max_length=16, choices=Uom.choices, default=Uom.KG)
    department = models.ForeignKey(
        "wpe_masters.DepartmentMaster",
        on_delete=models.PROTECT,
        related_name="production_bags",
        null=True,
        blank=True,
    )
    current_status = models.CharField(max_length=16, choices=BagStatus.choices, blank=True, default=BagStatus.FREE)

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "Bag Creation"
        verbose_name_plural = "Bag Creations"


class PackingMaterialMaster(ProductionCodeTrackedModel):
    class Uom(models.TextChoices):
        KG = "KG", "KG"
        NOS = "NOS", "Nos"

    code_prefix = "PM"
    code_width = 3

    item = models.ForeignKey(
        "wpe_masters.ItemMaster",
        on_delete=models.PROTECT,
        related_name="packing_materials",
    )
    uom = models.CharField(max_length=16, choices=Uom.choices)
    standard_consumption = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "Packing Material"
        verbose_name_plural = "Packing Materials"


class BOMCreationMaster(ProductionCodeTrackedModel):
    class OutputUom(models.TextChoices):
        NOS = "NOS", "Nos"
        KG = "KG", "KG"

    class BOMStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        APPROVED = "APPROVED", "Approved"

    code_prefix = "BOM"
    code_width = 3

    product = models.ForeignKey(
        "production.ProfileCreationMaster",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bom_creations",
    )
    bom_version = models.CharField(max_length=30, blank=True)
    output_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    output_uom = models.CharField(max_length=16, choices=OutputUom.choices, blank=True)
    status = models.CharField(max_length=16, choices=BOMStatus.choices, default=BOMStatus.DRAFT, db_index=True)

    class Meta(ProductionCodeTrackedModel.Meta):
        verbose_name = "BOM Creation"
        verbose_name_plural = "BOM Creations"


class BOMItemCreationMaster(models.Model):
    class ItemType(models.TextChoices):
        RM = "RM", "RM"
        PACKING = "PACKING", "Packing"
        CONSUMABLE = "CONSUMABLE", "Consumable"

    bom = models.ForeignKey(
        "production.BOMCreationMaster",
        on_delete=models.CASCADE,
        related_name="items",
    )
    item = models.ForeignKey(
        "wpe_masters.ItemMaster",
        on_delete=models.PROTECT,
        related_name="bom_item_creations",
    )
    item_type = models.CharField(max_length=16, choices=ItemType.choices)
    required_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    uom = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["bom__code", "item__item_code", "id"]
        verbose_name = "BOM Item Creation"
        verbose_name_plural = "BOM Item Creations"

    def __str__(self):
        return f"{self.bom.code} — {self.item.item_name}"

    def clean(self):
        super().clean()
        self.uom = str(self.uom or "").strip().upper()


class BOMVariant(models.Model):
    class RecipeStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        APPROVED = "APPROVED", "Approved"
        INACTIVE = "INACTIVE", "Inactive"

    variant_code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=255)
    product_item = models.ForeignKey("Items.Item", null=True, blank=True, on_delete=models.SET_NULL, related_name="bom_variants")
    revision = models.CharField(max_length=10, default="v1")
    batch_size = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    batch_uom = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=16, choices=RecipeStatus.choices, default=RecipeStatus.DRAFT, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_production_recipes",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    access_password_hash = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["variant_code"]

    def set_password(self, raw_password: str):
        self.access_password_hash = hashlib.sha256(raw_password.encode()).hexdigest()

    def check_password(self, raw_password: str) -> bool:
        return self.access_password_hash == hashlib.sha256(raw_password.encode()).hexdigest()

    @property
    def has_password(self) -> bool:
        return bool(self.access_password_hash)

    def __str__(self):
        return f"{self.variant_code} — {self.name}"

    def clean(self):
        super().clean()
        self.variant_code = str(self.variant_code or "").strip().upper()
        self.name = str(self.name or "").strip()
        self.revision = str(self.revision or "").strip() or "v1"
        self.batch_uom = str(self.batch_uom or "").strip().upper()
        self.notes = str(self.notes or "").strip()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.variant_code:
                self.variant_code = build_prefixed_running_number(
                    type(self),
                    field_name="variant_code",
                    prefix="REC",
                    width=3,
                    instance=self,
                )
            self.full_clean()
            return super().save(*args, **kwargs)


class BOMVariantComponent(models.Model):
    bom_variant = models.ForeignKey(BOMVariant, on_delete=models.CASCADE, related_name="components")
    item = models.ForeignKey("Items.Item", null=True, blank=True, on_delete=models.PROTECT)
    product_subtype = models.ForeignKey(
        "wpe_masters.ProductTypeSubtype",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bom_variant_components",
    )
    target_weight_grams = models.DecimalField(max_digits=10, decimal_places=3)
    min_weight_grams = models.DecimalField(max_digits=10, decimal_places=3)
    max_weight_grams = models.DecimalField(max_digits=10, decimal_places=3)
    sequence = models.PositiveIntegerField(default=1)
    is_regrind = models.BooleanField(default=False)
    unit = models.CharField(max_length=20, default="g")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.CheckConstraint(
                condition=Q(item__isnull=False) | Q(product_subtype__isnull=False),
                name="production_bom_component_source_required",
            ),
        ]

    def __str__(self):
        return f"{self.bom_variant.variant_code} — {self.component_name or f'Component {self.pk}'}"

    def clean(self):
        super().clean()
        if not self.item_id and not self.product_subtype_id:
            raise ValidationError("item or product_subtype is required.")

        if not self.bom_variant_id:
            return

        if self.target_weight_grams is None or Decimal(self.target_weight_grams) <= Decimal("0"):
            raise ValidationError({"target_weight_grams": "Standard weight must be greater than zero."})

        if self.min_weight_grams is None or Decimal(self.min_weight_grams) < Decimal("0"):
            raise ValidationError({"min_weight_grams": "Minimum weight must be zero or greater."})

        if self.max_weight_grams is None or Decimal(self.max_weight_grams) < Decimal("0"):
            raise ValidationError({"max_weight_grams": "Maximum weight must be zero or greater."})

        target_weight = Decimal(self.target_weight_grams)
        min_weight = Decimal(self.min_weight_grams)
        max_weight = Decimal(self.max_weight_grams)

        if min_weight > target_weight:
            raise ValidationError({"min_weight_grams": "Minimum weight cannot exceed standard weight."})

        if max_weight < target_weight:
            raise ValidationError({"max_weight_grams": "Maximum weight cannot be less than standard weight."})

        if min_weight > max_weight:
            raise ValidationError({"min_weight_grams": "Minimum weight cannot exceed maximum weight."})

        queryset = type(self).objects.filter(bom_variant_id=self.bom_variant_id)
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)

        if self.item_id and queryset.filter(item_id=self.item_id).exists():
            raise ValidationError({"item": "This item is already mapped to the recipe."})

        if self.product_subtype_id and queryset.filter(product_subtype_id=self.product_subtype_id).exists():
            raise ValidationError({"product_subtype": "This item sub category is already mapped to the recipe."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def source_type(self) -> str:
        return "PRODUCT_SUBTYPE" if self.product_subtype_id else "ITEM"

    @property
    def component_name(self) -> str:
        if self.product_subtype_id:
            return self.product_subtype.name
        if self.item_id:
            return self.item.item_name
        return ""

    @property
    def component_code(self) -> str:
        if self.product_subtype_id:
            return self.product_subtype.code
        if self.item_id:
            return self.item.item_code
        return ""

    @property
    def component_category_name(self) -> str:
        if self.product_subtype_id:
            return self.product_subtype.category.name
        if self.item_id:
            return self.item.category
        return ""

    @property
    def component_is_active(self) -> bool | None:
        if self.product_subtype_id:
            return bool(self.product_subtype.is_active and self.product_subtype.category.is_active)
        if self.item_id:
            return bool(self.item.status)
        return None


class ProductionOrderMaterialPlan(models.Model):
    class SourceType(models.TextChoices):
        ITEM = "ITEM", "Item"
        PRODUCT_SUBTYPE = "PRODUCT_SUBTYPE", "Product Subtype"

    production_order = models.ForeignKey(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="material_plans",
    )
    bom_variant = models.ForeignKey(BOMVariant, null=True, blank=True, on_delete=models.SET_NULL)
    bom_component = models.ForeignKey(BOMVariantComponent, null=True, blank=True, on_delete=models.SET_NULL)
    item = models.ForeignKey("Items.Item", null=True, blank=True, on_delete=models.SET_NULL)
    product_subtype = models.ForeignKey(
        "wpe_masters.ProductTypeSubtype",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="production_material_plans",
    )
    sequence = models.PositiveIntegerField(default=1)
    source_type = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.ITEM)
    is_bom_derived = models.BooleanField(default=False)
    is_manual = models.BooleanField(default=False)
    item_code = models.CharField(max_length=100, blank=True)
    item_name = models.CharField(max_length=255)
    unit = models.CharField(max_length=20, default="g")
    per_unit_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO_DECIMAL)
    bom_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO_DECIMAL)
    required_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO_DECIMAL)
    received_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO_DECIMAL)
    remaining_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO_DECIMAL)
    request_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO_DECIMAL)
    rate = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO_DECIMAL)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO_DECIMAL)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sequence", "id"]
        indexes = [
            models.Index(fields=["production_order", "sequence"], name="prod_material_order_seq_idx"),
            models.Index(fields=["bom_variant"], name="prod_material_bom_idx"),
        ]

    def __str__(self):
        return f"{self.production_order.production_id} — {self.item_name}"

    def clean(self):
        if self.source_type == self.SourceType.PRODUCT_SUBTYPE and not self.product_subtype_id and not self.bom_component_id:
            raise ValidationError({"product_subtype": "Product subtype rows must reference a BOM component or subtype."})

        if self.source_type == self.SourceType.ITEM and not (self.item_id or self.item_code):
            raise ValidationError({"item": "Item rows must include an item reference or item code."})

    def save(self, *args, **kwargs):
        if self.item_id:
            self.item_code = self.item.item_code
            self.item_name = self.item.item_name
            self.unit = self.unit or self.item.unit
        elif self.product_subtype_id:
            self.item_code = self.product_subtype.code
            self.item_name = self.product_subtype.name
        elif self.bom_component_id:
            self.item_code = self.bom_component.component_code
            self.item_name = self.bom_component.component_name
            self.unit = self.unit or self.bom_component.unit

        self.full_clean()
        return super().save(*args, **kwargs)


class ProductionBatch(models.Model):
    class Stage(models.TextChoices):
        AD = "AD", "Raw Materials (AD)"
        BL = "BL", "Blending (BL)"
        GL = "GL", "Granulation (GL)"

    class BatchStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    batch_no = models.CharField(max_length=30, unique=True, blank=True)
    workflow_batch_no = models.CharField(max_length=30, blank=True, null=True, db_index=True)
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name="batches")
    bom_variant = models.ForeignKey(BOMVariant, null=True, blank=True, on_delete=models.SET_NULL)
    stage = models.CharField(max_length=10, choices=Stage.choices)
    machine = models.ForeignKey(ProductionMachine, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=BatchStatus.choices, default=BatchStatus.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    operator = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["stage", "-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        updates = {}
        if not self.batch_no:
            self.batch_no = f"BATCH-{self.pk:08d}"
            updates["batch_no"] = self.batch_no
        if not self.workflow_batch_no:
            self.workflow_batch_no = self.batch_no
            updates["workflow_batch_no"] = self.workflow_batch_no
        if updates:
            ProductionBatch.objects.filter(pk=self.pk).update(**updates)

    def __str__(self):
        return self.batch_no or f"Batch-{self.pk}"


_WORKFLOW_SOURCE_BATCH_PATTERN = re.compile(r"Moved from [A-Z]+ batch ([A-Z0-9-]+)", re.IGNORECASE)


def _extract_workflow_batch_no_from_notes(notes: str) -> str:
    match = _WORKFLOW_SOURCE_BATCH_PATTERN.search(str(notes or ""))
    return str(match.group(1) if match else "").strip().rstrip(".")


def _batch_anchor_timestamp(batch: ProductionBatch) -> float:
    anchor = getattr(batch, "completed_at", None) or getattr(batch, "started_at", None) or getattr(batch, "created_at", None)
    return anchor.timestamp() if anchor else 0.0


def _resolve_related_batches(batch: ProductionBatch, sibling_batches=None) -> list[ProductionBatch]:
    if sibling_batches is not None:
        return list(sibling_batches)

    order = getattr(batch, "production_order", None)
    if order is None:
        return []

    prefetched_batches = getattr(order, "_prefetched_objects_cache", {}).get("batches")
    if prefetched_batches is not None:
        return list(prefetched_batches)

    return list(order.batches.all())


def resolve_workflow_batch_no(batch: ProductionBatch | None, sibling_batches=None, visited=None) -> str:
    if batch is None:
        return ""

    workflow_batch_no = str(getattr(batch, "workflow_batch_no", "") or "").strip()
    if workflow_batch_no:
        return workflow_batch_no

    source_batch_no = _extract_workflow_batch_no_from_notes(getattr(batch, "notes", ""))
    if source_batch_no:
        return source_batch_no

    batch_no = str(getattr(batch, "batch_no", "") or "").strip()
    previous_stage_by_stage = {
        ProductionBatch.Stage.BL: ProductionBatch.Stage.AD,
        ProductionBatch.Stage.GL: ProductionBatch.Stage.BL,
    }
    previous_stage = previous_stage_by_stage.get(getattr(batch, "stage", ""))
    if not previous_stage:
        return batch_no

    visited = set(visited or ())
    batch_key = getattr(batch, "pk", None) or f"unsaved-{id(batch)}"
    if batch_key in visited:
        return batch_no
    visited.add(batch_key)

    related_batches = _resolve_related_batches(batch, sibling_batches=sibling_batches)
    current_anchor_timestamp = _batch_anchor_timestamp(batch)
    candidates = [candidate for candidate in related_batches if candidate.pk != batch.pk and candidate.stage == previous_stage]
    if not candidates:
        return batch_no

    def sort_key(candidate: ProductionBatch):
        candidate_anchor = _batch_anchor_timestamp(candidate)
        is_not_after_current = current_anchor_timestamp == 0.0 or candidate_anchor <= current_anchor_timestamp
        return (
            1 if is_not_after_current else 0,
            candidate_anchor,
            getattr(candidate, "id", 0) or 0,
        )

    source_batch = max(candidates, key=sort_key)
    resolved_source_batch_no = resolve_workflow_batch_no(source_batch, sibling_batches=related_batches, visited=visited)
    return resolved_source_batch_no or batch_no


class ProductionOutputCapture(models.Model):
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name="output_captures")
    source_batch = models.OneToOneField(ProductionBatch, on_delete=models.CASCADE, related_name="output_capture")
    sequence = models.PositiveIntegerField()
    scancode_id = models.CharField(max_length=120, unique=True, db_index=True)
    recipe_no = models.CharField(max_length=100, blank=True)
    quantity_kg = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO_DECIMAL)
    weight_kg = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO_DECIMAL)
    binlot = models.CharField(max_length=100, blank=True)
    session_key = models.TextField(blank=True)
    captured_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-captured_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["production_order", "sequence"], name="prod_out_cap_ord_seq_uq"),
        ]
        indexes = [
            models.Index(fields=["production_order", "captured_at"], name="prod_out_cap_ord_cap_idx"),
        ]

    def __str__(self):
        return f"{self.production_order.production_id} — {self.scancode_id}"


class BatchWeightEntry(models.Model):
    batch = models.ForeignKey(ProductionBatch, on_delete=models.CASCADE, related_name="weight_entries")
    bom_component = models.ForeignKey(BOMVariantComponent, on_delete=models.PROTECT)
    item = models.ForeignKey("Items.Item", null=True, blank=True, on_delete=models.PROTECT)
    target_weight_grams = models.DecimalField(max_digits=10, decimal_places=3)
    entered_weight_grams = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    is_valid = models.BooleanField(null=True, blank=True)
    validation_notes = models.TextField(blank=True)
    source = models.CharField(max_length=20, default="MANUAL")
    entered_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    entered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("batch", "bom_component")]

    def validate_weight(self):
        if self.entered_weight_grams is None:
            self.is_valid = False
            self.validation_notes = "No weight entered."
            return

        entered_weight = Decimal(self.entered_weight_grams)
        component_unit = normalize_weight_unit(getattr(self.bom_component, "unit", "g"))
        recipe_min = Decimal(self.bom_component.min_weight_grams)
        recipe_max = Decimal(self.bom_component.max_weight_grams)
        global_min = Decimal(WEIGHT_MIN_GRAMS)
        global_max = Decimal(WEIGHT_MAX_GRAMS)
        validation_unit = "g"

        # Some legacy recipes still store gram-scale values even when the unit label is "kgs".
        # Only convert the global thresholds when the recipe bounds themselves are clearly kg-scale.
        if component_unit == "kg":
            kg_scaled_global_max = convert_gram_limit_to_component_unit(WEIGHT_MAX_GRAMS, component_unit)
            if recipe_max <= kg_scaled_global_max:
                global_min = convert_gram_limit_to_component_unit(WEIGHT_MIN_GRAMS, component_unit)
                global_max = kg_scaled_global_max
                validation_unit = component_unit
        errors = []
        if entered_weight < global_min:
            errors.append(f"Below global min {format_weight_value(global_min)}{validation_unit}.")
        if entered_weight > global_max:
            errors.append(f"Exceeds global max {format_weight_value(global_max)}{validation_unit}.")
        if entered_weight < recipe_min:
            errors.append(
                f"Below recipe min {format_weight_value(self.bom_component.min_weight_grams)}{component_unit}."
            )
        if entered_weight > recipe_max:
            errors.append(
                f"Exceeds recipe max {format_weight_value(self.bom_component.max_weight_grams)}{component_unit}."
            )
        self.is_valid = len(errors) == 0
        self.validation_notes = " ".join(errors)

    def __str__(self):
        return f"{self.batch} — {self.component_name}: {self.entered_weight_grams}g"

    @property
    def component_name(self) -> str:
        return self.bom_component.component_name

    @property
    def component_code(self) -> str:
        return self.bom_component.component_code

    @property
    def component_category_name(self) -> str:
        return self.bom_component.component_category_name


class RegrindMaterialEntry(models.Model):
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name="regrind_entries")
    batch = models.ForeignKey(ProductionBatch, on_delete=models.CASCADE, related_name="regrind_entries")
    stage = models.CharField(max_length=10, choices=ProductionBatch.Stage.choices)
    item = models.ForeignKey("Items.Item", on_delete=models.PROTECT)
    quantity_grams = models.DecimalField(max_digits=10, decimal_places=3)
    source_lot_no = models.CharField(max_length=50, blank=True)
    is_valid = models.BooleanField(default=True)
    validation_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    added_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.batch} — {self.item.item_code}: {self.quantity_grams}g"
