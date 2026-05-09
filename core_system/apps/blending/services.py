from __future__ import annotations

from apps.store.models import StoreStock
from apps.store.services import cancel_store_request, create_store_request, get_blending_warehouse


def create_blending_store_request(*, requested_by, items, remarks=None):
    return create_store_request(requested_by=requested_by, items=items, remarks=remarks)


def cancel_blending_store_request(request_id: int, cancelled_by, remarks: str | None = None):
    return cancel_store_request(request_id, cancelled_by, remarks=remarks)


def blending_stock_queryset():
    blending_warehouse = get_blending_warehouse()
    return (
        StoreStock.objects.select_related("item", "warehouse")
        .filter(warehouse=blending_warehouse, available_qty__gt=0)
        .order_by("item__item_name", "id")
    )
