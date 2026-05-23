from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.items.models import Item, STOCK_ZERO


class BlendingStock(models.Model):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name="blending_stock")
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

    def __str__(self):
        return f"{self.item.item_code} BLENDING {self.quantity}"


class BlendingInventoryMovementBase(models.Model):
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


class BlendingInward(BlendingInventoryMovementBase):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="blending_inward_entries")

    class Meta(BlendingInventoryMovementBase.Meta):
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=STOCK_ZERO),
                name="blending_inward_quantity_gt_zero",
            ),
        ]

    def __str__(self):
        return f"{self.item.item_code} BLENDING IN {self.quantity}"


class BlendingOutward(BlendingInventoryMovementBase):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="blending_outward_entries")

    class Meta(BlendingInventoryMovementBase.Meta):
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=STOCK_ZERO),
                name="blending_outward_quantity_gt_zero",
            ),
        ]

    def __str__(self):
        return f"{self.item.item_code} BLENDING OUT {self.quantity}"
