from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.items.models import Item, STOCK_ZERO


class UUIDAuditMixin(models.Model):
    unique_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Warehouse(UUIDAuditMixin):
    class WarehouseType(models.TextChoices):
        STORE = "STORE", "Store"
        BLENDING = "BLENDING", "Blending"
        GENERAL = "GENERAL", "General"
        QC_PENDING = "QC_PENDING", "QC Pending"
        REJECTED = "REJECTED", "Rejected"

    code = models.CharField(max_length=30, unique=True, db_index=True)
    name = models.CharField(max_length=120, db_index=True)
    warehouse_type = models.CharField(
        max_length=20,
        choices=WarehouseType.choices,
        default=WarehouseType.GENERAL,
        db_index=True,
    )
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_system = models.BooleanField(default=False)

    class Meta(UUIDAuditMixin.Meta):
        ordering = ["name", "id"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class StoreInventoryMovementBase(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    unit = models.CharField(max_length=50)
    date = models.DateField(default=timezone.localdate, db_index=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-date", "-id"]
        indexes = [
            models.Index(fields=["item", "date"]),
            models.Index(fields=["reference_number"]),
        ]


class StoreInward(StoreInventoryMovementBase):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="store_inward_entries")

    class Meta(StoreInventoryMovementBase.Meta):
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=STOCK_ZERO),
                name="store_inward_quantity_gt_zero",
            ),
        ]

    def __str__(self):
        return f"{self.item.item_code} STORE IN {self.quantity}"


class StoreOutward(StoreInventoryMovementBase):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="store_outward_entries")

    class Meta(StoreInventoryMovementBase.Meta):
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=STOCK_ZERO),
                name="store_outward_quantity_gt_zero",
            ),
        ]

    def __str__(self):
        return f"{self.item.item_code} STORE OUT {self.quantity}"


class StoreStock(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="inventory_stocks")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="current_stocks")
    available_qty = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=STOCK_ZERO,
        validators=[MinValueValidator(Decimal("0.000"))],
    )
    reserved_qty = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=STOCK_ZERO,
        validators=[MinValueValidator(Decimal("0.000"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["warehouse__name", "item__item_name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(available_qty__gte=STOCK_ZERO),
                name="store_stock_available_qty_gte_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_qty__gte=STOCK_ZERO),
                name="store_stock_reserved_qty_gte_zero",
            ),
            models.UniqueConstraint(
                fields=["item", "warehouse"],
                name="store_stock_item_warehouse_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["warehouse", "item"], name="store_stock_wh_item_idx"),
            models.Index(fields=["item", "warehouse"], name="store_stock_item_wh_idx"),
        ]

    @property
    def net_available_qty(self):
        net_available = self.available_qty - self.reserved_qty
        return net_available if net_available > STOCK_ZERO else STOCK_ZERO

    @property
    def quantity(self):
        return self.available_qty

    def __str__(self):
        return f"{self.item.item_code} {self.warehouse.code} {self.available_qty}"


class StoreTransaction(models.Model):
    class TransactionType(models.TextChoices):
        GRN_INWARD = "GRN_INWARD", "GRN Inward"
        OPENING_STOCK = "OPENING_STOCK", "Opening Stock"
        MANUAL_INWARD = "MANUAL_INWARD", "Manual Inward"
        MANUAL_OUTWARD = "MANUAL_OUTWARD", "Manual Outward"
        ADJUSTMENT_IN = "ADJUSTMENT_IN", "Adjustment In"
        ADJUSTMENT_OUT = "ADJUSTMENT_OUT", "Adjustment Out"
        SR_ISSUE = "SR_ISSUE", "Store Request Issue"
        SR_RECEIPT = "SR_RECEIPT", "Store Request Receipt"

    class ReferenceType(models.TextChoices):
        GRN = "GRN", "GRN"
        OPENING_STOCK = "OPENING_STOCK", "Opening Stock"
        MANUAL = "MANUAL", "Manual"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        STORE_REQUEST = "STORE_REQUEST", "Store Request"

    transaction_no = models.CharField(max_length=30, unique=True, blank=True, null=True, db_index=True)
    transaction_date = models.DateField(default=timezone.localdate, db_index=True)
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices, db_index=True)
    reference_type = models.CharField(max_length=30, choices=ReferenceType.choices, db_index=True)
    reference_id = models.CharField(max_length=100, blank=True, null=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="store_transactions")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_transactions")
    inward_qty = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=STOCK_ZERO,
        validators=[MinValueValidator(Decimal("0.000"))],
    )
    outward_qty = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=STOCK_ZERO,
        validators=[MinValueValidator(Decimal("0.000"))],
    )
    balance_qty = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=STOCK_ZERO,
        validators=[MinValueValidator(Decimal("0.000"))],
    )
    remarks = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_store_transactions",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(inward_qty__gte=STOCK_ZERO),
                name="store_tx_inward_qty_gte_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(outward_qty__gte=STOCK_ZERO),
                name="store_tx_outward_qty_gte_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(balance_qty__gte=STOCK_ZERO),
                name="store_tx_balance_qty_gte_zero",
            ),
            models.CheckConstraint(
                condition=(
                    (models.Q(inward_qty=STOCK_ZERO) & models.Q(outward_qty__gt=STOCK_ZERO))
                    | (models.Q(inward_qty__gt=STOCK_ZERO) & models.Q(outward_qty=STOCK_ZERO))
                ),
                name="store_tx_single_direction_qty",
            ),
        ]
        indexes = [
            models.Index(fields=["warehouse", "item", "transaction_date"], name="store_tx_wh_item_date_idx"),
            models.Index(fields=["transaction_type", "reference_id"], name="store_tx_type_ref_idx"),
            models.Index(fields=["reference_type", "reference_id"], name="store_tx_ref_type_ref_idx"),
        ]

    @property
    def movement_qty(self):
        return self.inward_qty if self.inward_qty > STOCK_ZERO else self.outward_qty

    @property
    def quantity(self):
        return self.movement_qty

    def __str__(self):
        return f"{self.transaction_no or 'PENDING'} {self.item.item_code} {self.transaction_type}"


class StockRequest(models.Model):
    class RequestType(models.TextChoices):
        GENERAL = "GENERAL", "General"
        ADDITIVE = "ADDITIVE", "Additive"

    class Status(models.TextChoices):
        PENDING_HEAD_APPROVAL = "PENDING_HEAD_APPROVAL", "Pending Head Approval"
        PENDING_REQUEST_PROCESS = "PENDING_REQUEST_PROCESS", "Pending Request Process"
        PENDING_STOCK_RELEASE = "PENDING_STOCK_RELEASE", "Pending Stock Release"
        HEAD_REJECTED = "HEAD_REJECTED", "Rejected by Head"
        REQUEST_REJECTED = "REQUEST_REJECTED", "Rejected During Request Process"
        RELEASE_REJECTED = "RELEASE_REJECTED", "Rejected During Stock Release"
        CLOSED_WON = "CLOSED_WON", "Closed Won"
        CANCELLED = "CANCELLED", "Cancelled"

    request_no = models.CharField(max_length=30, unique=True, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.PENDING_HEAD_APPROVAL, db_index=True)
    requesting_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="requested_store_requests",
        null=True,
        blank=True,
    )
    request_type = models.CharField(
        max_length=20,
        choices=RequestType.choices,
        default=RequestType.GENERAL,
        db_index=True,
    )
    department = models.CharField(max_length=100, default="BLENDING")
    request_date = models.DateField(default=timezone.localdate, db_index=True)
    require_date = models.DateField(null=True, blank=True, db_index=True)
    require_time = models.TimeField(null=True, blank=True)
    requested_for_name = models.CharField(max_length=255, blank=True)
    request_reason = models.TextField(blank=True)
    issuing_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="issued_store_requests",
        null=True,
        blank=True,
    )
    remarks = models.TextField(blank=True, null=True)
    approval_remarks = models.TextField(blank=True, null=True)
    head_approval_remarks = models.TextField(blank=True, null=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_store_stock_requests",
    )
    action_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="actioned_store_stock_requests",
        null=True,
        blank=True,
    )
    head_action_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="head_reviewed_stock_requests",
        null=True,
        blank=True,
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="cancelled_store_stock_requests",
        null=True,
        blank=True,
    )
    release_action_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="released_store_stock_requests",
        null=True,
        blank=True,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    action_at = models.DateTimeField(null=True, blank=True)
    head_action_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    release_action_at = models.DateTimeField(null=True, blank=True)
    release_remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [
            models.Index(fields=["status", "requested_at"], name="store_request_status_date_idx"),
            models.Index(fields=["request_no"], name="store_request_no_idx"),
            models.Index(fields=["request_type", "department"], name="store_request_type_dept_idx"),
        ]

    def __str__(self):
        return self.request_no or f"SR-{self.pk or 'NEW'}"

    @property
    def item(self):
        first_item = self.items.order_by("id").select_related("item").first()
        return first_item.item if first_item else None

    @property
    def quantity(self):
        first_item = self.items.order_by("id").first()
        return first_item.requested_qty if first_item else STOCK_ZERO

    @property
    def approved_by(self):
        return self.action_by

    @property
    def approved_at(self):
        return self.action_at


class StockRequestItem(UUIDAuditMixin):
    stock_request = models.ForeignKey(StockRequest, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="store_request_items")
    requested_qty = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    approved_qty = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=STOCK_ZERO,
        validators=[MinValueValidator(Decimal("0.000"))],
    )
    issued_qty = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=STOCK_ZERO,
        validators=[MinValueValidator(Decimal("0.000"))],
    )
    remarks = models.TextField(blank=True, null=True)

    class Meta(UUIDAuditMixin.Meta):
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(requested_qty__gt=STOCK_ZERO),
                name="stock_request_item_requested_qty_gt_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(approved_qty__gte=STOCK_ZERO),
                name="stock_request_item_approved_qty_gte_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(issued_qty__gte=STOCK_ZERO),
                name="stock_request_item_issued_qty_gte_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(approved_qty__lte=models.F("requested_qty")),
                name="stock_request_item_approved_lte_requested",
            ),
            models.CheckConstraint(
                condition=models.Q(issued_qty__lte=models.F("approved_qty")),
                name="stock_request_item_issued_lte_approved",
            ),
            models.UniqueConstraint(
                fields=["stock_request", "item"],
                name="stock_request_item_unique_item_per_request",
            ),
        ]
        indexes = [
            models.Index(fields=["stock_request", "item"], name="sr_item_req_idx"),
        ]

    def __str__(self):
        return f"{self.stock_request.request_no or self.stock_request_id} - {self.item.item_code}"
