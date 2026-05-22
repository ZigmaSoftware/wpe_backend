from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


ZERO_DECIMAL = Decimal("0.000")


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


class ProductionMachine(models.Model):
    class MachineType(models.TextChoices):
        HIGH_SPEED_MIX = "HIGH_SPEED_MIX", "High Speed Mix"
        GRANULATOR = "GRANULATOR", "Granulator"

    machine_code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    machine_type = models.CharField(max_length=30, choices=MachineType.choices)
    applicable_stages = models.CharField(max_length=20, default="AD,BL")
    is_active = models.BooleanField(default=True)
    location = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["machine_code"]

    def __str__(self):
        return f"{self.machine_code} — {self.name}"


class BOMVariant(models.Model):
    variant_code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=255)
    product_item = models.ForeignKey("Items.Item", null=True, blank=True, on_delete=models.SET_NULL, related_name="bom_variants")
    revision = models.CharField(max_length=10, default="v1")
    is_active = models.BooleanField(default=True)
    access_password_hash = models.CharField(max_length=64)
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

    def __str__(self):
        return f"{self.variant_code} — {self.name}"


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
        if not self.item_id and not self.product_subtype_id:
            raise ValidationError("item or product_subtype is required.")

        if not self.bom_variant_id:
            return

        queryset = type(self).objects.filter(bom_variant_id=self.bom_variant_id)
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)

        if self.item_id and queryset.filter(item_id=self.item_id).exists():
            raise ValidationError({"item": "This item is already mapped to the BOM variant."})

        if self.product_subtype_id and queryset.filter(product_subtype_id=self.product_subtype_id).exists():
            raise ValidationError({"product_subtype": "This product subtype is already mapped to the BOM variant."})

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
        if not self.batch_no:
            self.batch_no = f"BATCH-{self.pk:08d}"
            ProductionBatch.objects.filter(pk=self.pk).update(batch_no=self.batch_no)

    def __str__(self):
        return self.batch_no or f"Batch-{self.pk}"


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
        w = float(self.entered_weight_grams)
        errors = []
        if w < WEIGHT_MIN_GRAMS:
            errors.append(f"Below global min {WEIGHT_MIN_GRAMS}g.")
        if w > WEIGHT_MAX_GRAMS:
            errors.append(f"Exceeds global max {WEIGHT_MAX_GRAMS}g.")
        if w < float(self.bom_component.min_weight_grams):
            errors.append(f"Below recipe min {self.bom_component.min_weight_grams}g.")
        if w > float(self.bom_component.max_weight_grams):
            errors.append(f"Exceeds recipe max {self.bom_component.max_weight_grams}g.")
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
