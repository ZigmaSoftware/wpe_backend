from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.items.models import Item, STOCK_ZERO
from common.grn_client import GRNServiceClient
from common.rbac import ADMIN_ROLE_TOKENS, user_has_role

from .models import StockRequest, StockRequestItem, StoreStock, StoreTransaction, Warehouse


STOCK_QUANTIZER = Decimal("0.001")
STORE_WAREHOUSE_CODE = "STORE"
BLENDING_WAREHOUSE_CODE = "BLENDING"
AUTO_CREATED_ITEM_CATEGORY = "GRN Imported"
AUTO_CREATED_ITEM_GROUP = "Inbound GRN"
AUTO_CREATED_ITEM_SUB_GROUP = "Auto Created"
MOVED_TO_GRN_SCOPES = {"moved to grn", "moved_to_grn", "moved-grn", "grn", "approved", "grn approved", "grn_approved"}

INWARD_TRANSACTION_TYPES = {
    StoreTransaction.TransactionType.GRN_INWARD,
    StoreTransaction.TransactionType.OPENING_STOCK,
    StoreTransaction.TransactionType.MANUAL_INWARD,
    StoreTransaction.TransactionType.ADJUSTMENT_IN,
    StoreTransaction.TransactionType.SR_RECEIPT,
}
OUTWARD_TRANSACTION_TYPES = {
    StoreTransaction.TransactionType.MANUAL_OUTWARD,
    StoreTransaction.TransactionType.ADJUSTMENT_OUT,
    StoreTransaction.TransactionType.SR_ISSUE,
}


def quantize_stock(value: Decimal | int | float | str) -> Decimal:
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError({"quantity": "Quantity must be a valid decimal value."}) from exc
    return decimal_value.quantize(STOCK_QUANTIZER)


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_unit(value: Any) -> str:
    return normalize_text(value).upper().replace(" ", "")


def ensure_item_unit(item: Item) -> None:
    if not normalize_text(item.unit):
        raise ValidationError({"item_id": "Item unit is required for inventory transactions."})


def require_persisted_user(user, *, field_name: str) -> None:
    if getattr(user, "pk", None) is None and getattr(user, "id", None) is None:
        raise ValidationError({field_name: "A persisted authenticated user is required for this action."})


def get_or_create_system_warehouse(
    *,
    code: str,
    name: str,
    warehouse_type: str,
) -> Warehouse:
    warehouse, _created = Warehouse.objects.get_or_create(
        code=code,
        defaults={
            "name": name,
            "warehouse_type": warehouse_type,
            "is_active": True,
            "is_system": True,
        },
    )
    return warehouse


def get_store_warehouse() -> Warehouse:
    return get_or_create_system_warehouse(
        code=STORE_WAREHOUSE_CODE,
        name="Main Store",
        warehouse_type=Warehouse.WarehouseType.STORE,
    )


def get_warehouse_by_name(name: str) -> Warehouse:
    """Look up an active warehouse by display name; auto-create if missing."""
    stripped = name.strip()
    warehouse = Warehouse.objects.filter(name=stripped, is_active=True).first()
    if warehouse:
        return warehouse
    warehouse = Warehouse.objects.filter(name__iexact=stripped, is_active=True).first()
    if warehouse:
        return warehouse
    code = re.sub(r"[^A-Z0-9]+", "_", stripped.upper())[:30].strip("_")
    name_upper = stripped.upper()
    if "QC" in name_upper or "PENDING" in name_upper:
        wh_type = Warehouse.WarehouseType.QC_PENDING
    elif "REJECT" in name_upper:
        wh_type = Warehouse.WarehouseType.REJECTED
    else:
        wh_type = Warehouse.WarehouseType.STORE
    warehouse, _created = Warehouse.objects.get_or_create(
        code=code,
        defaults={
            "name": stripped,
            "warehouse_type": wh_type,
            "is_active": True,
            "is_system": True,
        },
    )
    return warehouse


def resolve_target_warehouse(grn_payload: dict[str, Any], *, accepted: bool = True) -> Warehouse:
    """Resolve the correct warehouse for stock posting based on QCR outcome."""
    if accepted:
        name = normalize_text(grn_payload.get("target_warehouse") or "Stores")
        if name.upper() == STORE_WAREHOUSE_CODE or name.lower() in {"stores", "main store", "store"}:
            return get_store_warehouse()
        return get_warehouse_by_name(name)
    else:
        name = normalize_text(grn_payload.get("target_warehouse") or "Rejected Warehouse - CBE")
        return get_warehouse_by_name(name)


def get_blending_warehouse() -> Warehouse:
    return get_or_create_system_warehouse(
        code=BLENDING_WAREHOUSE_CODE,
        name="Blending Floor",
        warehouse_type=Warehouse.WarehouseType.BLENDING,
    )


def assign_request_no(stock_request: StockRequest) -> StockRequest:
    if not stock_request.request_no:
        stock_request.request_no = f"SR-{stock_request.pk:08d}"
        stock_request.save(update_fields=["request_no"])
    return stock_request


def assign_transaction_no(stock_transaction: StoreTransaction) -> StoreTransaction:
    if not stock_transaction.transaction_no:
        stock_transaction.transaction_no = f"STX-{stock_transaction.pk:08d}"
        stock_transaction.save(update_fields=["transaction_no"])
    return stock_transaction


def get_current_stock(
    *,
    item: Item,
    warehouse: Warehouse,
    lock_for_update: bool = False,
) -> StoreStock:
    queryset = StoreStock.objects.select_related("item", "warehouse")
    if lock_for_update:
        queryset = queryset.select_for_update()

    stock_row = queryset.filter(item=item, warehouse=warehouse).first()
    if stock_row is not None:
        return stock_row

    try:
        stock_row = StoreStock.objects.create(
            item=item,
            warehouse=warehouse,
            available_qty=STOCK_ZERO,
            reserved_qty=STOCK_ZERO,
        )
    except IntegrityError:
        stock_row = StoreStock.objects.select_related("item", "warehouse").get(item=item, warehouse=warehouse)

    if lock_for_update:
        return StoreStock.objects.select_related("item", "warehouse").select_for_update().get(pk=stock_row.pk)
    return stock_row


def calculate_available_qty(*, item: Item, warehouse: Warehouse) -> Decimal:
    stock_row = get_current_stock(item=item, warehouse=warehouse, lock_for_update=False)
    return quantize_stock(stock_row.available_qty)


def _validate_transaction_type(transaction_type: str, *, movement_type: str) -> None:
    if movement_type == "inward" and transaction_type not in INWARD_TRANSACTION_TYPES:
        raise ValidationError({"transaction_type": "Invalid inward transaction type."})
    if movement_type == "outward" and transaction_type not in OUTWARD_TRANSACTION_TYPES:
        raise ValidationError({"transaction_type": "Invalid outward transaction type."})


def _apply_stock_movement(
    *,
    item: Item,
    warehouse: Warehouse,
    quantity: Decimal | int | float | str,
    movement_type: str,
    transaction_type: str,
    reference_type: str,
    reference_id: str | None = None,
    remarks: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_by=None,
    transaction_date=None,
    locked_stock: StoreStock | None = None,
) -> tuple[StoreStock, StoreTransaction]:
    quantity = quantize_stock(quantity)
    if quantity <= STOCK_ZERO:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    _validate_transaction_type(transaction_type, movement_type=movement_type)
    ensure_item_unit(item)

    current_stock = locked_stock or get_current_stock(item=item, warehouse=warehouse, lock_for_update=True)
    available_qty = quantize_stock(current_stock.available_qty)

    if movement_type == "inward":
        inward_qty = quantity
        outward_qty = STOCK_ZERO
        balance_qty = available_qty + quantity
    elif movement_type == "outward":
        inward_qty = STOCK_ZERO
        outward_qty = quantity
        balance_qty = available_qty - quantity
        if balance_qty < STOCK_ZERO:
            raise ValidationError(
                {
                    "quantity": (
                        f"Insufficient stock in {warehouse.code}. "
                        f"Available quantity is {available_qty} and requested quantity is {quantity}."
                    )
                }
            )
    else:
        raise ValidationError({"movement_type": "Invalid stock movement type."})

    current_stock.available_qty = balance_qty
    current_stock.save(update_fields=["available_qty", "updated_at"])

    stock_transaction = StoreTransaction.objects.create(
        transaction_date=transaction_date or timezone.localdate(),
        transaction_type=transaction_type,
        reference_type=reference_type,
        reference_id=reference_id or None,
        item=item,
        warehouse=warehouse,
        inward_qty=inward_qty,
        outward_qty=outward_qty,
        balance_qty=balance_qty,
        remarks=remarks or None,
        metadata=metadata or {},
        created_by=created_by if getattr(created_by, "pk", None) else None,
    )
    assign_transaction_no(stock_transaction)
    return current_stock, stock_transaction


def apply_inward_stock(
    *,
    item: Item,
    warehouse: Warehouse,
    quantity,
    transaction_type: str,
    reference_type: str,
    reference_id: str | None = None,
    remarks: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_by=None,
    transaction_date=None,
) -> tuple[StoreStock, StoreTransaction]:
    with transaction.atomic():
        return _apply_stock_movement(
            item=item,
            warehouse=warehouse,
            quantity=quantity,
            movement_type="inward",
            transaction_type=transaction_type,
            reference_type=reference_type,
            reference_id=reference_id,
            remarks=remarks,
            metadata=metadata,
            created_by=created_by,
            transaction_date=transaction_date,
        )


def apply_outward_stock(
    *,
    item: Item,
    warehouse: Warehouse,
    quantity,
    transaction_type: str,
    reference_type: str,
    reference_id: str | None = None,
    remarks: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_by=None,
    transaction_date=None,
) -> tuple[StoreStock, StoreTransaction]:
    with transaction.atomic():
        return _apply_stock_movement(
            item=item,
            warehouse=warehouse,
            quantity=quantity,
            movement_type="outward",
            transaction_type=transaction_type,
            reference_type=reference_type,
            reference_id=reference_id,
            remarks=remarks,
            metadata=metadata,
            created_by=created_by,
            transaction_date=transaction_date,
        )


def transfer_stock(
    *,
    item: Item,
    quantity,
    source_warehouse: Warehouse,
    destination_warehouse: Warehouse,
    reference_type: str,
    reference_id: str,
    remarks: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_by=None,
    transaction_date=None,
) -> dict[str, Any]:
    with transaction.atomic():
        source_stock = get_current_stock(item=item, warehouse=source_warehouse, lock_for_update=True)
        destination_stock = get_current_stock(item=item, warehouse=destination_warehouse, lock_for_update=True)

        source_stock, issue_transaction = _apply_stock_movement(
            item=item,
            warehouse=source_warehouse,
            quantity=quantity,
            movement_type="outward",
            transaction_type=StoreTransaction.TransactionType.SR_ISSUE,
            reference_type=reference_type,
            reference_id=reference_id,
            remarks=remarks,
            metadata={
                **(metadata or {}),
                "destination_warehouse": destination_warehouse.code,
            },
            created_by=created_by,
            transaction_date=transaction_date,
            locked_stock=source_stock,
        )
        destination_stock, receipt_transaction = _apply_stock_movement(
            item=item,
            warehouse=destination_warehouse,
            quantity=quantity,
            movement_type="inward",
            transaction_type=StoreTransaction.TransactionType.SR_RECEIPT,
            reference_type=reference_type,
            reference_id=reference_id,
            remarks=remarks,
            metadata={
                **(metadata or {}),
                "source_warehouse": source_warehouse.code,
            },
            created_by=created_by,
            transaction_date=transaction_date,
            locked_stock=destination_stock,
        )

    return {
        "source_stock": source_stock,
        "destination_stock": destination_stock,
        "issue_transaction": issue_transaction,
        "receipt_transaction": receipt_transaction,
    }


def build_request_line_reference(stock_request: StockRequest, request_item: StockRequestItem) -> str:
    return f"{stock_request.request_no}:{request_item.id}"


def calculate_request_availability(stock_request: StockRequest) -> dict[int, Decimal]:
    issuing_warehouse = stock_request.issuing_warehouse or get_store_warehouse()
    item_ids = [request_item.item_id for request_item in stock_request.items.all()]
    availability: dict[int, Decimal] = {}
    for stock_row in StoreStock.objects.filter(warehouse=issuing_warehouse, item_id__in=item_ids).values(
        "item_id",
        "available_qty",
    ):
        availability[stock_row["item_id"]] = stock_row["available_qty"] or STOCK_ZERO
    return availability


def create_store_request(
    *,
    requested_by,
    items: list[dict[str, Any]],
    remarks: str | None = None,
    request_type: str = StockRequest.RequestType.GENERAL,
    department: str = "BLENDING",
    request_date=None,
    require_date=None,
    require_time=None,
    requested_for_name: str = "",
    request_reason: str = "",
) -> StockRequest:
    require_persisted_user(requested_by, field_name="requested_by")
    requesting_warehouse = get_blending_warehouse()
    issuing_warehouse = get_store_warehouse()

    if not items:
        raise ValidationError({"items": "At least one store request item is required."})

    with transaction.atomic():
        stock_request = StockRequest.objects.create(
            requesting_warehouse=requesting_warehouse,
            issuing_warehouse=issuing_warehouse,
            request_type=request_type,
            department=normalize_text(department) or "BLENDING",
            request_date=request_date or timezone.localdate(),
            require_date=require_date,
            require_time=require_time,
            requested_for_name=normalize_text(requested_for_name),
            request_reason=normalize_text(request_reason),
            remarks=normalize_text(remarks) or None,
            requested_by=requested_by,
        )
        assign_request_no(stock_request)

        request_items = []
        for row in items:
            item = row["item"]
            quantity = quantize_stock(row["quantity"])
            if quantity <= STOCK_ZERO:
                raise ValidationError({"quantity": "Quantity must be greater than zero."})
            ensure_item_unit(item)
            request_items.append(
                StockRequestItem(
                    stock_request=stock_request,
                    item=item,
                    requested_qty=quantity,
                    remarks=normalize_text(row.get("remarks")) or None,
                )
            )
        StockRequestItem.objects.bulk_create(request_items)

    return (
        StockRequest.objects.select_related(
            "requesting_warehouse",
            "issuing_warehouse",
            "requested_by",
            "action_by",
            "cancelled_by",
        )
        .prefetch_related("items__item")
        .get(pk=stock_request.pk)
    )


def request_stock(
    *,
    item: Item,
    quantity: Decimal | int | float | str,
    user,
    request_type: str = StockRequest.RequestType.GENERAL,
    department: str = "BLENDING",
    request_date=None,
    require_date=None,
    require_time=None,
    requested_for_name: str = "",
    request_reason: str = "",
) -> StockRequest:
    return create_store_request(
        requested_by=user,
        items=[{"item": item, "quantity": quantity}],
        remarks=None,
        request_type=request_type,
        department=department,
        request_date=request_date,
        require_date=require_date,
        require_time=require_time,
        requested_for_name=requested_for_name,
        request_reason=request_reason,
    )


def update_store_request(
    request_id: int,
    *,
    requested_by,
    items: list[dict[str, Any]],
    remarks: str | None = None,
    request_type: str = StockRequest.RequestType.GENERAL,
    department: str = "BLENDING",
    request_date=None,
    require_date=None,
    require_time=None,
    requested_for_name: str = "",
    request_reason: str = "",
) -> StockRequest:
    require_persisted_user(requested_by, field_name="requested_by")

    if not items:
        raise ValidationError({"items": "At least one store request item is required."})

    with transaction.atomic():
        stock_request = (
            StockRequest.objects.select_related("requested_by")
            .prefetch_related("items__item")
            .select_for_update()
            .get(pk=request_id)
        )
        if stock_request.status != StockRequest.Status.PENDING:
            raise ValidationError({"status": "Only pending store requests can be edited."})

        if stock_request.requested_by_id != getattr(requested_by, "id", None) and not user_has_role(
            requested_by,
            ADMIN_ROLE_TOKENS,
        ):
            raise ValidationError({"detail": "You can edit only your own pending store requests."})

        request_items = []
        for row in items:
            item = row["item"]
            quantity = quantize_stock(row["quantity"])
            if quantity <= STOCK_ZERO:
                raise ValidationError({"quantity": "Quantity must be greater than zero."})
            ensure_item_unit(item)
            request_items.append(
                StockRequestItem(
                    stock_request=stock_request,
                    item=item,
                    requested_qty=quantity,
                    remarks=normalize_text(row.get("remarks")) or None,
                )
            )

        stock_request.request_type = request_type
        stock_request.department = normalize_text(department) or "BLENDING"
        stock_request.request_date = request_date or stock_request.request_date or timezone.localdate()
        stock_request.require_date = require_date
        stock_request.require_time = require_time
        stock_request.requested_for_name = normalize_text(requested_for_name)
        stock_request.request_reason = normalize_text(request_reason)
        stock_request.remarks = normalize_text(remarks) or None
        stock_request.save(
            update_fields=[
                "request_type",
                "department",
                "request_date",
                "require_date",
                "require_time",
                "requested_for_name",
                "request_reason",
                "remarks",
            ]
        )

        stock_request.items.all().delete()
        StockRequestItem.objects.bulk_create(request_items)

    return (
        StockRequest.objects.select_related(
            "requesting_warehouse",
            "issuing_warehouse",
            "requested_by",
            "action_by",
            "cancelled_by",
        )
        .prefetch_related("items__item")
        .get(pk=request_id)
    )


def cancel_store_request(request_id: int, cancelled_by, remarks: str | None = None) -> StockRequest:
    require_persisted_user(cancelled_by, field_name="cancelled_by")

    with transaction.atomic():
        stock_request = (
            StockRequest.objects.select_related("requested_by")
            .prefetch_related("items__item")
            .select_for_update()
            .get(pk=request_id)
        )
        if stock_request.status != StockRequest.Status.PENDING:
            raise ValidationError({"status": "Only pending store requests can be cancelled."})

        if stock_request.requested_by_id != getattr(cancelled_by, "id", None) and not user_has_role(
            cancelled_by,
            ADMIN_ROLE_TOKENS,
        ):
            raise ValidationError({"detail": "You can cancel only your own pending store requests."})

        stock_request.status = StockRequest.Status.CANCELLED
        stock_request.cancelled_by = cancelled_by
        stock_request.cancelled_at = timezone.now()
        if remarks:
            stock_request.approval_remarks = normalize_text(remarks)
        stock_request.save(
            update_fields=[
                "status",
                "cancelled_by",
                "cancelled_at",
                "approval_remarks",
            ]
        )

    return stock_request


def approve_stock_request(request_id: int, approver, approval_remarks: str | None = None) -> dict[str, Any]:
    require_persisted_user(approver, field_name="action_by")

    with transaction.atomic():
        stock_request = (
            StockRequest.objects.select_related("requesting_warehouse", "issuing_warehouse", "requested_by")
            .prefetch_related("items__item")
            .select_for_update()
            .get(pk=request_id)
        )
        if stock_request.status != StockRequest.Status.PENDING:
            raise ValidationError({"status": "Only pending store requests can be approved."})

        issuing_warehouse = stock_request.issuing_warehouse or get_store_warehouse()
        requesting_warehouse = stock_request.requesting_warehouse or get_blending_warehouse()

        shortages = []
        locked_source_stocks: dict[int, StoreStock] = {}
        for request_item in stock_request.items.all():
            source_stock = get_current_stock(
                item=request_item.item,
                warehouse=issuing_warehouse,
                lock_for_update=True,
            )
            locked_source_stocks[request_item.item_id] = source_stock
            available_qty = quantize_stock(source_stock.available_qty)
            if available_qty < request_item.requested_qty:
                shortages.append(
                    {
                        "item_id": request_item.item_id,
                        "item_code": request_item.item.item_code,
                        "item_name": request_item.item.item_name,
                        "requested_qty": request_item.requested_qty,
                        "available_qty": available_qty,
                        "shortage_qty": request_item.requested_qty - available_qty,
                    }
                )

        if shortages:
            raise ValidationError(
                {
                    "items": shortages,
                    "detail": "Insufficient stock is available for one or more request items.",
                }
            )

        issue_transactions: list[StoreTransaction] = []
        receipt_transactions: list[StoreTransaction] = []
        source_stocks: list[StoreStock] = []
        destination_stocks: list[StoreStock] = []

        for request_item in stock_request.items.all():
            destination_stock = get_current_stock(
                item=request_item.item,
                warehouse=requesting_warehouse,
                lock_for_update=True,
            )
            reference_id = build_request_line_reference(stock_request, request_item)

            source_stock, issue_transaction = _apply_stock_movement(
                item=request_item.item,
                warehouse=issuing_warehouse,
                quantity=request_item.requested_qty,
                movement_type="outward",
                transaction_type=StoreTransaction.TransactionType.SR_ISSUE,
                reference_type=StoreTransaction.ReferenceType.STORE_REQUEST,
                reference_id=reference_id,
                remarks=approval_remarks,
                metadata={
                    "stock_request_id": stock_request.id,
                    "stock_request_item_id": request_item.id,
                    "destination_warehouse": requesting_warehouse.code,
                },
                created_by=approver,
                transaction_date=timezone.localdate(),
                locked_stock=locked_source_stocks[request_item.item_id],
            )
            destination_stock, receipt_transaction = _apply_stock_movement(
                item=request_item.item,
                warehouse=requesting_warehouse,
                quantity=request_item.requested_qty,
                movement_type="inward",
                transaction_type=StoreTransaction.TransactionType.SR_RECEIPT,
                reference_type=StoreTransaction.ReferenceType.STORE_REQUEST,
                reference_id=reference_id,
                remarks=approval_remarks,
                metadata={
                    "stock_request_id": stock_request.id,
                    "stock_request_item_id": request_item.id,
                    "source_warehouse": issuing_warehouse.code,
                },
                created_by=approver,
                transaction_date=timezone.localdate(),
                locked_stock=destination_stock,
            )

            request_item.approved_qty = request_item.requested_qty
            request_item.issued_qty = request_item.requested_qty
            request_item.save(update_fields=["approved_qty", "issued_qty", "updated_at"])

            source_stocks.append(source_stock)
            destination_stocks.append(destination_stock)
            issue_transactions.append(issue_transaction)
            receipt_transactions.append(receipt_transaction)

        stock_request.status = StockRequest.Status.APPROVED
        stock_request.approval_remarks = normalize_text(approval_remarks) or None
        stock_request.action_by = approver
        stock_request.action_at = timezone.now()
        stock_request.save(update_fields=["status", "approval_remarks", "action_by", "action_at"])

    return {
        "stock_request": (
            StockRequest.objects.select_related(
                "requesting_warehouse",
                "issuing_warehouse",
                "requested_by",
                "action_by",
                "cancelled_by",
            )
            .prefetch_related("items__item")
            .get(pk=stock_request.pk)
        ),
        "source_stocks": source_stocks,
        "destination_stocks": destination_stocks,
        "issue_transactions": issue_transactions,
        "receipt_transactions": receipt_transactions,
    }


def reject_stock_request(request_id: int, approver, approval_remarks: str | None = None) -> StockRequest:
    require_persisted_user(approver, field_name="action_by")

    with transaction.atomic():
        stock_request = (
            StockRequest.objects.prefetch_related("items__item")
            .select_for_update()
            .get(pk=request_id)
        )
        if stock_request.status != StockRequest.Status.PENDING:
            raise ValidationError({"status": "Only pending store requests can be rejected."})

        stock_request.status = StockRequest.Status.REJECTED
        stock_request.approval_remarks = normalize_text(approval_remarks) or None
        stock_request.action_by = approver
        stock_request.action_at = timezone.now()
        stock_request.save(update_fields=["status", "approval_remarks", "action_by", "action_at"])

    return stock_request


def resolve_grn_identifier(grn_payload: dict[str, Any]) -> str:
    document_details = grn_payload.get("document_details", {}) if isinstance(grn_payload, dict) else {}
    return str(
        grn_payload.get("unique_id")
        or grn_payload.get("id")
        or document_details.get("grn_no")
        or grn_payload.get("grn_no")
        or ""
    ).strip()


def resolve_grn_process_status(grn_payload: dict[str, Any]) -> str:
    if not isinstance(grn_payload, dict):
        return ""

    document_details = grn_payload.get("document_details")
    qcr_details = grn_payload.get("qcr")
    status_candidates = [
        grn_payload.get("process_status"),
        grn_payload.get("qcr_status"),
        qcr_details.get("status") if isinstance(qcr_details, dict) else None,
        document_details.get("process_status") if isinstance(document_details, dict) else None,
    ]

    for status_value in status_candidates:
        normalized_status = normalize_text(status_value).lower()
        if normalized_status:
            return normalized_status

    return ""


def ensure_grn_ready_for_store_sync(grn_payload: dict[str, Any]) -> None:
    process_status = resolve_grn_process_status(grn_payload)
    if process_status not in MOVED_TO_GRN_SCOPES:
        raise ValidationError(
            {
                "process_status": "Store stock can only be synced after QCR is moved to GRN.",
            }
        )


def extract_grn_lines(grn_payload: dict[str, Any]) -> list[dict[str, Any]]:
    lines = grn_payload.get("items")
    if isinstance(lines, list) and lines:
        return [line for line in lines if isinstance(line, dict)]
    return [grn_payload]


def resolve_item_for_grn_line(grn_payload: dict[str, Any], line_payload: dict[str, Any]) -> Item:
    external_item_id_text = normalize_text(line_payload.get("item_id") or grn_payload.get("item_id"))
    product_description = normalize_text(
        line_payload.get("product_description")
        or line_payload.get("item_name")
        or grn_payload.get("product_description")
    )
    unit = normalize_text(line_payload.get("unit") or grn_payload.get("unit"))
    hsn_code = normalize_text(line_payload.get("hsn_code") or grn_payload.get("hsn_code"))

    item_by_external_id = None
    if external_item_id_text:
        item_by_external_id = Item.objects.filter(external_item_id__iexact=external_item_id_text).first()
        if item_by_external_id is None and external_item_id_text.isdigit():
            item_by_external_id = Item.objects.filter(pk=int(external_item_id_text)).first()
        if item_by_external_id is None:
            item_by_external_id = Item.objects.filter(item_code__iexact=external_item_id_text).first()

    name_matches = (
        list(Item.objects.filter(item_name__iexact=product_description).order_by("id")[:2])
        if product_description
        else []
    )
    item_by_name = name_matches[0] if len(name_matches) == 1 else None

    if len(name_matches) > 1 and item_by_external_id is None:
        raise ValidationError(
            {
                "product_description": (
                    "Multiple items with this product name already exist. "
                    "Use a unique sender item_id to identify the correct product."
                )
            }
        )

    if item_by_external_id is not None and item_by_name is not None and item_by_external_id.pk != item_by_name.pk:
        raise ValidationError(
            {
                "item_id": "Sender item ID matches a different item than the product name provided.",
                "product_description": "Product name matches a different item than the sender item ID provided.",
            }
        )

    item = item_by_external_id or item_by_name
    if item is not None:
        if external_item_id_text and not normalize_text(item.external_item_id):
            item.external_item_id = external_item_id_text
            item.save(update_fields=["external_item_id", "updated_at"])
        return item

    if not product_description:
        raise ValidationError({"product_description": "Product description is required to create a new item."})
    if not unit:
        raise ValidationError({"unit": "Unit is required to create a new item."})

    return Item.objects.create(
        product_type=Item.PRODUCT_TYPE_GENERAL,
        category=AUTO_CREATED_ITEM_CATEGORY,
        group=AUTO_CREATED_ITEM_GROUP,
        sub_group=AUTO_CREATED_ITEM_SUB_GROUP,
        item_name=product_description,
        external_item_id=external_item_id_text or None,
        hsn_code=hsn_code or None,
        unit=unit,
        product_details=f"Auto-created from GRN {resolve_grn_identifier(grn_payload)}",
        description=f"Imported from supplier GRN payload for {product_description}.",
    )


def build_grn_reference_id(grn_identifier: str, line_number: int) -> str:
    return f"{grn_identifier}:{line_number}"


def add_stock_from_grn(grn_payload: dict[str, Any], *, created_by=None) -> dict[str, Any]:
    if not isinstance(grn_payload, dict):
        raise ValidationError({"payload": "GRN payload must be a JSON object."})

    use_rejected_qty = bool(grn_payload.get("use_rejected_qty"))
    accepted = not use_rejected_qty

    if accepted:
        ensure_grn_ready_for_store_sync(grn_payload)

    grn_identifier = resolve_grn_identifier(grn_payload)
    if not grn_identifier:
        raise ValidationError({"reference_id": "GRN payload must include a stable grn_no, id, or unique_id."})

    document_details = grn_payload.get("document_details", {}) if isinstance(grn_payload, dict) else {}
    grn_date = document_details.get("grn_date") or grn_payload.get("grn_date") or timezone.localdate()
    supplier_name = (
        (grn_payload.get("supplier_details") or {}).get("trade_name")
        or grn_payload.get("trade_name")
        or "GRN Supplier"
    )
    target_warehouse = resolve_target_warehouse(grn_payload, accepted=accepted)

    processed_references: list[str] = []
    skipped_references: list[str] = []
    store_transactions: list[StoreTransaction] = []

    with transaction.atomic():
        for line_number, line_payload in enumerate(extract_grn_lines(grn_payload), start=1):
            reference_id = build_grn_reference_id(grn_identifier, line_number)
            item = resolve_item_for_grn_line(grn_payload, line_payload)
            ensure_item_unit(item)

            if StoreTransaction.objects.filter(
                item=item,
                warehouse=target_warehouse,
                transaction_type=StoreTransaction.TransactionType.GRN_INWARD,
                reference_type=StoreTransaction.ReferenceType.GRN,
                reference_id=reference_id,
            ).exists():
                skipped_references.append(reference_id)
                continue

            source_unit = line_payload.get("unit") or grn_payload.get("unit")
            if source_unit and normalize_unit(source_unit) != normalize_unit(item.unit):
                raise ValidationError(
                    {
                        "unit": (
                            f"GRN unit '{source_unit}' does not match item unit '{item.unit}' "
                            f"for item {item.item_code}."
                        )
                    }
                )

            if use_rejected_qty:
                raw_quantity = (
                    line_payload.get("rejected_qty")
                    or grn_payload.get("rejected_qty")
                )
            else:
                raw_quantity = (
                    line_payload.get("accepted_qty")
                    or line_payload.get("quantity")
                    or line_payload.get("total_quantity")
                    or grn_payload.get("accepted_qty")
                    or grn_payload.get("quantity")
                    or grn_payload.get("total_quantity")
                )

            if not raw_quantity:
                skipped_references.append(reference_id)
                continue

            quantity = quantize_stock(raw_quantity)
            if quantity <= STOCK_ZERO:
                skipped_references.append(reference_id)
                continue

            remarks = (
                f"GRN rejected stock from {supplier_name}" if use_rejected_qty
                else f"GRN inward from {supplier_name}"
            )
            _stock_row, stock_transaction = _apply_stock_movement(
                item=item,
                warehouse=target_warehouse,
                quantity=quantity,
                movement_type="inward",
                transaction_type=StoreTransaction.TransactionType.GRN_INWARD,
                reference_type=StoreTransaction.ReferenceType.GRN,
                reference_id=reference_id,
                remarks=remarks,
                metadata={
                    "grn_no": document_details.get("grn_no") or grn_payload.get("grn_no"),
                    "grn_identifier": grn_identifier,
                    "supplier": supplier_name,
                    "line_number": line_number,
                    "raw_line": line_payload,
                    "qc_outcome": "rejected" if use_rejected_qty else "accepted",
                    "target_warehouse": target_warehouse.code,
                },
                created_by=created_by,
                transaction_date=grn_date,
                locked_stock=get_current_stock(item=item, warehouse=target_warehouse, lock_for_update=True),
            )
            store_transactions.append(stock_transaction)
            processed_references.append(reference_id)

    return {
        "grn_identifier": grn_identifier,
        "processed_references": processed_references,
        "skipped_references": skipped_references,
        "store_transaction_ids": [transaction_row.id for transaction_row in store_transactions],
    }


def sync_grn_stock(*, grn_no: str | None = None, created_by=None) -> list[dict[str, Any]]:
    client = GRNServiceClient()
    response = client.fetch_grn(grn_no=grn_no)
    payloads = response.get("data") if isinstance(response, dict) else response

    if isinstance(payloads, dict):
        payload_list = [payloads]
    elif isinstance(payloads, list):
        payload_list = payloads
    else:
        payload_list = []

    return [add_stock_from_grn(payload, created_by=created_by) for payload in payload_list if isinstance(payload, dict)]
