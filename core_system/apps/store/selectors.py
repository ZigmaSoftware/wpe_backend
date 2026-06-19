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
        "head_action_by",
        "cancelled_by",
        "release_action_by",
    ).prefetch_related("items__item")


def current_stock_queryset():
    return StoreStock.objects.select_related("item", "warehouse")


def _coerce_source_text(value) -> str:
    return str(value or "").strip()


def _transaction_group_reference(transaction_row: StoreTransaction) -> str:
    metadata = transaction_row.metadata or {}
    reference_id = _coerce_source_text(transaction_row.reference_id)
    grn_identifier = _coerce_source_text(metadata.get("grn_identifier"))
    grn_no = _coerce_source_text(metadata.get("grn_no"))

    if grn_no:
        return grn_no
    if grn_identifier:
        return grn_identifier
    if transaction_row.reference_type == StoreTransaction.ReferenceType.GRN and ":" in reference_id:
        return reference_id.rsplit(":", 1)[0]
    return reference_id or transaction_row.reference_type


def _serialize_stock_source(transaction_row: StoreTransaction) -> dict:
    metadata = transaction_row.metadata or {}
    reference = _transaction_group_reference(transaction_row)
    supplier = _coerce_source_text(metadata.get("supplier"))

    return {
        "source_group_key": f"{transaction_row.reference_type}:{reference}",
        "source_reference": reference,
        "source_supplier": supplier,
        "source_line_number": metadata.get("line_number"),
        "source_transaction_type": transaction_row.transaction_type,
        "source_transaction_no": transaction_row.transaction_no,
        "source_transaction_date": transaction_row.transaction_date,
        "source_created_at": transaction_row.created_at,
    }


def stock_source_map_for_stock_rows(stock_rows) -> dict[tuple[int, int], dict]:
    rows = list(stock_rows)
    if not rows:
        return {}

    warehouse_ids = {row.warehouse_id for row in rows}
    item_ids = {row.item_id for row in rows}
    source_map: dict[tuple[int, int], dict] = {}

    transactions = (
        StoreTransaction.objects.filter(
            warehouse_id__in=warehouse_ids,
            item_id__in=item_ids,
            inward_qty__gt=STOCK_ZERO,
        )
        .order_by("warehouse_id", "item_id", "-transaction_date", "-created_at", "-id")
    )
    for transaction_row in transactions:
        key = (transaction_row.warehouse_id, transaction_row.item_id)
        if key not in source_map:
            source_map[key] = _serialize_stock_source(transaction_row)

    return source_map


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
