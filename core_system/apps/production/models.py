from decimal import Decimal
from django.db import models
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
