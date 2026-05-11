from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from apps.items.models import STOCK_ZERO

from .models import StockRequest, StoreStock, StoreTransaction, Warehouse


def store_request_queryset():
    return StockRequest.objects.select_related(
        "requesting_warehouse",
        "issuing_warehouse",
        "requested_by",
        "action_by",
        "cancelled_by",
    ).prefetch_related("items__item")


def current_stock_queryset():
    return StoreStock.objects.select_related("item", "warehouse")


def stock_ledger_queryset():
    return StoreTransaction.objects.select_related("item", "warehouse", "created_by")


def availability_map_for_request_items(item_ids, warehouse: Warehouse) -> dict[int, Decimal]:
    if not item_ids:
        return {}

    return {
        row["item_id"]: row["available_qty"] or STOCK_ZERO
        for row in StoreStock.objects.filter(warehouse=warehouse, item_id__in=item_ids).values("item_id", "available_qty")
    }


def availability_map_for_requests(store_requests) -> dict[tuple[int | None, int], Decimal]:
    request_pairs = {
        (stock_request.issuing_warehouse_id, request_item.item_id)
        for stock_request in store_requests
        for request_item in stock_request.items.all()
    }
    if not request_pairs:
        return {}

    warehouse_ids = {warehouse_id for warehouse_id, _item_id in request_pairs if warehouse_id}
    item_ids = {item_id for _warehouse_id, item_id in request_pairs}
    availability_map = {
        (row["warehouse_id"], row["item_id"]): row["available_qty"] or STOCK_ZERO
        for row in StoreStock.objects.filter(
            warehouse_id__in=warehouse_ids,
            item_id__in=item_ids,
        ).values("warehouse_id", "item_id", "available_qty")
    }
    for pair in request_pairs:
        availability_map.setdefault(pair, STOCK_ZERO)
    return availability_map


def stock_dashboard_summary():
    warehouse_rows = (
        StoreStock.objects.select_related("warehouse")
        .values("warehouse_id", "warehouse__code", "warehouse__name")
        .annotate(
            available_qty_total=Sum("available_qty"),
            reserved_qty_total=Sum("reserved_qty"),
        )
        .order_by("warehouse__name", "warehouse_id")
    )
    return [
        {
            "warehouse_id": row["warehouse_id"],
            "warehouse_code": row["warehouse__code"],
            "warehouse_name": row["warehouse__name"],
            "available_qty_total": row["available_qty_total"] or STOCK_ZERO,
            "reserved_qty_total": row["reserved_qty_total"] or STOCK_ZERO,
        }
        for row in warehouse_rows
    ]
