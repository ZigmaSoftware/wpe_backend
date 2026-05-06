from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

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
