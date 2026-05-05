from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.items.models import Item, STOCK_ZERO


class DepartmentStock(models.Model):
    class Department(models.TextChoices):
        STORE = "STORE", "Store"
        BLENDING = "BLENDING", "Blending"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="department_stocks")
    department = models.CharField(max_length=20, choices=Department.choices, default=Department.STORE)
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=STOCK_ZERO,
        validators=[MinValueValidator(Decimal("0.000"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["item_id", "department"]
        unique_together = (("item", "department"),)
        indexes = [
            models.Index(fields=["department", "item"], name="blend_dept_item_idx"),
        ]

    def __str__(self):
        return f"{self.item.item_code} {self.department} {self.quantity}"


class StockTransfer(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        REJECTED = "REJECTED", "Rejected"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="stock_transfers")
    from_department = models.CharField(max_length=20, choices=DepartmentStock.Department.choices)
    to_department = models.CharField(max_length=20, choices=DepartmentStock.Department.choices)
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [
            models.Index(fields=["item", "status"], name="blend_transfer_item_status_idx"),
            models.Index(fields=["requested_at"], name="blend_transfer_requested_idx"),
        ]

    def __str__(self):
        return (
            f"{self.item.item_code} {self.from_department}->{self.to_department} "
            f"{self.quantity} [{self.status}]"
        )
