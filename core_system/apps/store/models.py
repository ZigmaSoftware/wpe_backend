from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.items.models import Item, STOCK_ZERO


class StoreStock(models.Model):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name="store_stock")
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=STOCK_ZERO,
        validators=[MinValueValidator(Decimal("0.000"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["item_id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=STOCK_ZERO),
                name="store_stock_quantity_gte_zero",
            ),
        ]

    def __str__(self):
        return f"{self.item.item_code} STORE {self.quantity}"


class StoreTransaction(models.Model):
    class TransactionType(models.TextChoices):
        GRN_IN = "GRN_IN", "GRN In"
        TRANSFER_OUT = "TRANSFER_OUT", "Transfer Out"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="store_transactions")
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    reference_id = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=Decimal("0.001")),
                name="store_tx_quantity_gt_zero",
            ),
            models.UniqueConstraint(
                fields=["transaction_type", "reference_id"],
                name="store_tx_type_reference_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["item", "transaction_type"], name="store_tx_item_type_idx"),
            models.Index(fields=["reference_id"], name="store_tx_reference_idx"),
            models.Index(fields=["created_at"], name="store_tx_created_idx"),
        ]

    def __str__(self):
        return f"{self.item.item_code} {self.transaction_type} {self.quantity}"


class StockRequest(models.Model):
    class RequestType(models.TextChoices):
        GENERAL = "GENERAL", "General"
        ADDITIVE = "ADDITIVE", "Additive"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="store_stock_requests")
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    request_type = models.CharField(
        max_length=20,
        choices=RequestType.choices,
        default=RequestType.GENERAL,
    )
    department = models.CharField(max_length=100, default="BLENDING")
    requested_for_name = models.CharField(max_length=255, blank=True)
    request_reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_store_stock_requests",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_store_stock_requests",
        null=True,
        blank=True,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=Decimal("0.001")),
                name="store_request_quantity_gt_zero",
            ),
        ]
        indexes = [
            models.Index(fields=["item", "status"], name="store_request_item_status_idx"),
            models.Index(fields=["requested_at"], name="store_request_created_idx"),
        ]

    def __str__(self):
        return f"{self.item.item_code} request {self.quantity} [{self.status}]"
