from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.items.models import Item, STOCK_ZERO, ItemStockTransaction
from apps.store.services import create_item_stock_transaction, ensure_item_unit, quantize_stock

from .models import BlendingStock


BLENDING_WAREHOUSE = "BLENDING"


def get_blending_stock(
    item_id: int,
    *,
    item: Item | None = None,
    lock_for_update: bool = False,
) -> BlendingStock:
    if item is None:
        item_queryset = Item.objects.select_for_update() if lock_for_update else Item.objects
        item = item_queryset.get(pk=item_id)

    stock_queryset = BlendingStock.objects.select_related("item")
    if lock_for_update:
        stock_queryset = stock_queryset.select_for_update()

    blending_stock = stock_queryset.filter(item=item).first()
    if blending_stock is not None:
        return blending_stock

    try:
        blending_stock = BlendingStock.objects.create(item=item, quantity=STOCK_ZERO)
    except IntegrityError:
        blending_stock = BlendingStock.objects.select_related("item").get(item=item)

    if lock_for_update:
        return BlendingStock.objects.select_related("item").select_for_update().get(pk=blending_stock.pk)

    return blending_stock


def add_blending_stock(
    *,
    quantity: Decimal | int | float | str,
    metadata: dict,
    reference_id: str,
    item: Item | None = None,
    locked_item: Item | None = None,
) -> tuple[BlendingStock, ItemStockTransaction]:
    quantity = quantize_stock(quantity)
    if quantity <= STOCK_ZERO:
        raise ValidationError({"quantity": "Stock quantity must be greater than zero."})

    with transaction.atomic():
        locked = locked_item or item
        if locked is None:
            raise ValueError("item is required to add blending stock.")
        ensure_item_unit(locked)
        blending_stock = get_blending_stock(locked.id, item=locked, lock_for_update=True)
        blending_stock.quantity = quantize_stock(blending_stock.quantity) + quantity
        blending_stock.save(update_fields=["quantity", "updated_at"])

        stock_transaction = create_item_stock_transaction(
            item=locked,
            quantity=quantity,
            movement_type="inward",
            metadata={**metadata, "ref_id": reference_id, "warehouse": BLENDING_WAREHOUSE},
            warehouse=BLENDING_WAREHOUSE,
            balance=blending_stock.quantity,
        )

    return blending_stock, stock_transaction
