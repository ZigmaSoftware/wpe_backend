from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.items.models import Item, STOCK_ZERO

from .models import DepartmentStock, StockTransfer


STOCK_QUANTIZER = Decimal("0.001")
TRANSFER_CONTACT = "Blending Stock Transfer"
TRANSFER_BIN = "DEPT"


def quantize_department_stock(value: Decimal | int | float | str) -> Decimal:
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError({"quantity": "Stock quantity must be a valid decimal value."}) from exc

    return decimal_value.quantize(STOCK_QUANTIZER)


def normalize_department(department: str) -> str:
    normalized_department = str(department or "").strip().upper()
    valid_departments = set(DepartmentStock.Department.values)

    if normalized_department not in valid_departments:
        valid_values = ", ".join(sorted(valid_departments))
        raise ValidationError({"department": f"Invalid department. Use one of: {valid_values}."})

    return normalized_department


def get_department_stock(
    item_id: int,
    department: str,
    *,
    item: Item | None = None,
    lock_for_update: bool = False,
) -> DepartmentStock:
    department = normalize_department(department)

    if item is None:
        item_queryset = Item.objects.select_for_update() if lock_for_update else Item.objects
        item = item_queryset.get(pk=item_id)

    stock_queryset = DepartmentStock.objects.select_related("item")
    if lock_for_update:
        stock_queryset = stock_queryset.select_for_update()

    department_stock = stock_queryset.filter(item=item, department=department).first()
    if department_stock is not None:
        return department_stock

    default_quantity = item.current_stock if department == DepartmentStock.Department.STORE else STOCK_ZERO
    department_stock = DepartmentStock.objects.create(
        item=item,
        department=department,
        quantity=default_quantity,
    )

    if lock_for_update:
        return DepartmentStock.objects.select_related("item").select_for_update().get(pk=department_stock.pk)

    return department_stock


def transfer_stock(
    item_id: int,
    quantity: Decimal | int | float | str,
    from_dept: str = DepartmentStock.Department.STORE,
    to_dept: str = DepartmentStock.Department.BLENDING,
):
    from apps.items.views import record_stock_movement

    quantity = quantize_department_stock(quantity)
    if quantity <= STOCK_ZERO:
        raise ValidationError({"quantity": "Stock quantity must be greater than zero."})

    from_dept = normalize_department(from_dept)
    to_dept = normalize_department(to_dept)

    if from_dept == to_dept:
        raise ValidationError({"to_department": "Source and destination departments must be different."})

    with transaction.atomic():
        item = Item.objects.select_for_update().get(pk=item_id)
        from_stock = get_department_stock(item_id=item.id, department=from_dept, item=item, lock_for_update=True)
        to_stock = get_department_stock(item_id=item.id, department=to_dept, item=item, lock_for_update=True)

        if from_stock.quantity < quantity:
            raise ValidationError({"quantity": f"Insufficient stock in {from_dept} department."})

        transfer_out_metadata = {
            "date": timezone.localdate(),
            "trans_type": f"TRANSFER OUT ({to_dept})",
            "contact": TRANSFER_CONTACT,
            "warehouse": from_dept,
            "bin": TRANSFER_BIN,
        }
        transfer_in_metadata = {
            "date": timezone.localdate(),
            "trans_type": f"TRANSFER IN ({from_dept})",
            "contact": TRANSFER_CONTACT,
            "warehouse": to_dept,
            "bin": TRANSFER_BIN,
        }

        item, transfer_out_transaction = record_stock_movement(
            item_id=item.id,
            movement_type="outward",
            quantity=quantity,
            metadata=transfer_out_metadata,
            department=from_dept,
            locked_item=item,
            locked_department_stock=from_stock,
        )
        item, transfer_in_transaction = record_stock_movement(
            item_id=item.id,
            movement_type="inward",
            quantity=quantity,
            metadata=transfer_in_metadata,
            department=to_dept,
            locked_item=item,
            locked_department_stock=to_stock,
        )

        transfer = StockTransfer.objects.create(
            item=item,
            from_department=from_dept,
            to_department=to_dept,
            quantity=quantity,
            status=StockTransfer.Status.COMPLETED,
            completed_at=timezone.now(),
        )

    return transfer, from_stock, to_stock, transfer_out_transaction, transfer_in_transaction
