from __future__ import annotations

from django.db.models import Q

from apps.store.models import StoreStock
from apps.store.services import (
    cancel_store_request,
    create_store_request,
    get_blending_warehouse,
    get_store_warehouse,
    update_store_request,
)


BLENDING_DEPARTMENT = "BLENDING"


def is_additive_item(item) -> bool:
    searchable = " ".join(
        [
            str(item.category or ""),
            str(item.group or ""),
            str(item.sub_group or ""),
            str(item.item_name or ""),
        ]
    ).lower()
    return "additive" in searchable


def additive_item_query() -> Q:
    return (
        Q(item__category__icontains="additive")
        | Q(item__group__icontains="additive")
        | Q(item__sub_group__icontains="additive")
        | Q(item__item_name__icontains="additive")
    )


def create_blending_store_request(
    *,
    requested_by,
    items,
    remarks=None,
    request_type="GENERAL",
    department=BLENDING_DEPARTMENT,
    requested_for_name="",
    request_reason="",
):
    return create_store_request(
        requested_by=requested_by,
        items=items,
        remarks=remarks,
        request_type=request_type,
        department=department,
        requested_for_name=requested_for_name,
        request_reason=request_reason,
    )


def cancel_blending_store_request(request_id: int, cancelled_by, remarks: str | None = None):
    return cancel_store_request(request_id, cancelled_by, remarks=remarks)


def update_blending_store_request(
    request_id: int,
    *,
    requested_by,
    items,
    remarks=None,
    request_type="GENERAL",
    department=BLENDING_DEPARTMENT,
    requested_for_name="",
    request_reason="",
):
    return update_store_request(
        request_id,
        requested_by=requested_by,
        items=items,
        remarks=remarks,
        request_type=request_type,
        department=department,
        requested_for_name=requested_for_name,
        request_reason=request_reason,
    )


def blending_stock_queryset():
    blending_warehouse = get_blending_warehouse()
    return (
        StoreStock.objects.select_related("item", "warehouse")
        .filter(warehouse=blending_warehouse, available_qty__gt=0)
        .order_by("item__item_name", "id")
    )


def requestable_additive_stock_queryset():
    store_warehouse = get_store_warehouse()
    return (
        StoreStock.objects.select_related("item", "warehouse")
        .filter(warehouse=store_warehouse, available_qty__gt=0)
        .filter(additive_item_query())
        .order_by("item__item_name", "id")
    )
