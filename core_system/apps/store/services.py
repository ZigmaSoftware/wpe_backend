from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.items.models import Item, ItemStockTransaction, STOCK_ZERO
from common.grn_client import GRNServiceClient

from .models import StockRequest, StoreStock, StoreTransaction


STOCK_QUANTIZER = Decimal("0.001")
DEFAULT_STOCK_CONTACT = "Inventory Control"
DEFAULT_STOCK_BIN = "GEN"
STORE_WAREHOUSE = "STORE"
GRN_CONTACT = "GRN Service"
GRN_BIN = "GRN"
TRANSFER_CONTACT = "Store Stock Transfer"
TRANSFER_BIN = "DEPT"
AUTO_CREATED_ITEM_CATEGORY = "GRN Imported"
AUTO_CREATED_ITEM_GROUP = "Inbound GRN"
AUTO_CREATED_ITEM_SUB_GROUP = "Auto Created"


def quantize_stock(value: Decimal | int | float | str) -> Decimal:
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError({"quantity": "Stock quantity must be a valid decimal value."}) from exc

    return decimal_value.quantize(STOCK_QUANTIZER)


def normalize_unit(value: Any) -> str:
    return str(value or "").strip().upper().replace(" ", "")


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def ensure_item_unit(item: Item) -> None:
    if not str(item.unit or "").strip():
        raise ValidationError({"item_id": "Item unit is required for inventory transactions."})


def require_persisted_user(user, *, field_name: str) -> None:
    if getattr(user, "pk", None) is None and getattr(user, "id", None) is None:
        raise ValidationError({field_name: "A persisted authenticated user is required for this action."})


def get_store_stock(
    item_id: int,
    *,
    item: Item | None = None,
    lock_for_update: bool = False,
) -> StoreStock:
    if item is None:
        item_queryset = Item.objects.select_for_update() if lock_for_update else Item.objects
        item = item_queryset.get(pk=item_id)

    stock_queryset = StoreStock.objects.select_related("item")
    if lock_for_update:
        stock_queryset = stock_queryset.select_for_update()

    store_stock = stock_queryset.filter(item=item).first()
    if store_stock is not None:
        return store_stock

    try:
        store_stock = StoreStock.objects.create(
            item=item,
            quantity=quantize_stock(item.current_stock),
        )
    except IntegrityError:
        store_stock = StoreStock.objects.select_related("item").get(item=item)

    if lock_for_update:
        return StoreStock.objects.select_related("item").select_for_update().get(pk=store_stock.pk)

    return store_stock


def create_item_stock_transaction(
    *,
    item: Item,
    quantity: Decimal,
    movement_type: str,
    metadata: dict[str, Any],
    warehouse: str,
    balance: Decimal,
) -> ItemStockTransaction:
    return ItemStockTransaction.objects.create(
        item=item,
        date=metadata.get("date") or timezone.localdate(),
        ref_id=metadata.get("ref_id"),
        trans_type=metadata.get("trans_type") or (
            "stock movement inward" if movement_type == "inward" else "stock movement outward"
        ),
        sale_type=metadata.get("sale_type"),
        doc_id=metadata.get("doc_id"),
        contact=metadata.get("contact") or DEFAULT_STOCK_CONTACT,
        warehouse=metadata.get("warehouse") or warehouse,
        bin=metadata.get("bin") or DEFAULT_STOCK_BIN,
        inwards=quantity if movement_type == "inward" else STOCK_ZERO,
        outwards=quantity if movement_type == "outward" else STOCK_ZERO,
        balance=balance,
    )


def record_store_stock_movement(
    *,
    item_id: int,
    movement_type: str,
    quantity: Decimal | int | float | str,
    metadata: dict[str, Any],
    locked_item: Item | None = None,
    locked_store_stock: StoreStock | None = None,
) -> tuple[Item, StoreStock, ItemStockTransaction]:
    quantity = quantize_stock(quantity)
    if quantity <= STOCK_ZERO:
        raise ValidationError({"quantity": "Stock quantity must be greater than zero."})

    with transaction.atomic():
        item = locked_item or Item.objects.select_for_update().get(pk=item_id)
        ensure_item_unit(item)
        store_stock = locked_store_stock or get_store_stock(item.id, item=item, lock_for_update=True)
        current_stock = quantize_stock(store_stock.quantity)

        if movement_type == "inward":
            balance = current_stock + quantity
        elif movement_type == "outward":
            balance = current_stock - quantity
        else:
            raise ValueError("Invalid stock movement type.")

        if balance < STOCK_ZERO:
            raise ValidationError({"quantity": "Insufficient stock in STORE."})

        store_stock.quantity = balance
        store_stock.save(update_fields=["quantity", "updated_at"])

        item.current_stock = balance
        item.save(update_fields=["current_stock", "updated_at"])

        stock_transaction = create_item_stock_transaction(
            item=item,
            quantity=quantity,
            movement_type=movement_type,
            metadata=metadata,
            warehouse=STORE_WAREHOUSE,
            balance=balance,
        )

    return item, store_stock, stock_transaction


def resolve_grn_identifier(grn_payload: dict[str, Any]) -> str:
    document_details = grn_payload.get("document_details", {}) if isinstance(grn_payload, dict) else {}
    return str(
        grn_payload.get("unique_id")
        or grn_payload.get("id")
        or document_details.get("grn_no")
        or grn_payload.get("grn_no")
        or ""
    ).strip()


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

    name_matches = list(Item.objects.filter(item_name__iexact=product_description).order_by("id")[:2]) if product_description else []
    item_by_name = name_matches[0] if len(name_matches) == 1 else None

    if len(name_matches) > 1 and item_by_external_id is None:
        raise ValidationError(
            {
                "product_description": (
                    "Multiple items with this product name already exist in the store app. "
                    "Use a unique sender item_id to identify the correct product."
                )
            }
        )

    if item_by_external_id is not None and item_by_name is not None and item_by_external_id.pk != item_by_name.pk:
        raise ValidationError(
            {
                "item_id": "Sender item ID matches a different store item than the product name provided.",
                "product_description": "Product name matches a different store item than the sender item ID provided.",
            }
        )

    item = item_by_external_id or item_by_name
    if item is not None:
        if external_item_id_text and not normalize_text(item.external_item_id):
            item.external_item_id = external_item_id_text
            item.save(update_fields=["external_item_id", "updated_at"])
        return item

    if not product_description:
        raise ValidationError({"product_description": "Product description is required to create a new store item."})
    if not unit:
        raise ValidationError({"unit": "Unit is required to create a new store item."})

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


def add_stock_from_grn(grn_payload: dict[str, Any]) -> dict[str, Any]:
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

    processed_references: list[str] = []
    skipped_references: list[str] = []
    store_transactions: list[StoreTransaction] = []

    with transaction.atomic():
        for line_number, line_payload in enumerate(extract_grn_lines(grn_payload), start=1):
            reference_id = build_grn_reference_id(grn_identifier, line_number)

            if StoreTransaction.objects.filter(
                transaction_type=StoreTransaction.TransactionType.GRN_IN,
                reference_id=reference_id,
            ).exists():
                skipped_references.append(reference_id)
                continue

            item = resolve_item_for_grn_line(grn_payload, line_payload)
            ensure_item_unit(item)

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

            raw_quantity = (
                line_payload.get("accepted_qty")
                or line_payload.get("quantity")
                or line_payload.get("total_quantity")
                or grn_payload.get("accepted_qty")
                or grn_payload.get("quantity")
                or grn_payload.get("total_quantity")
            )
            quantity = quantize_stock(raw_quantity)
            if quantity <= STOCK_ZERO:
                skipped_references.append(reference_id)
                continue

            metadata = {
                "date": grn_date,
                "ref_id": reference_id,
                "trans_type": "GRN inward",
                "contact": GRN_CONTACT,
                "warehouse": STORE_WAREHOUSE,
                "bin": GRN_BIN,
                "grn_no": document_details.get("grn_no") or grn_payload.get("grn_no"),
                "grn_identifier": grn_identifier,
                "supplier": supplier_name,
                "line_number": line_number,
            }

            record_store_stock_movement(
                item_id=item.id,
                movement_type="inward",
                quantity=quantity,
                metadata=metadata,
            )

            store_transaction = StoreTransaction.objects.create(
                item=item,
                transaction_type=StoreTransaction.TransactionType.GRN_IN,
                quantity=quantity,
                reference_id=reference_id,
                metadata={
                    "grn_no": metadata["grn_no"],
                    "grn_identifier": grn_identifier,
                    "supplier": supplier_name,
                    "line_number": line_number,
                    "raw_line": line_payload,
                },
            )
            store_transactions.append(store_transaction)
            processed_references.append(reference_id)

    return {
        "grn_identifier": grn_identifier,
        "processed_references": processed_references,
        "skipped_references": skipped_references,
        "store_transaction_ids": [transaction_row.id for transaction_row in store_transactions],
    }


def sync_grn_stock(*, grn_no: str | None = None) -> list[dict[str, Any]]:
    client = GRNServiceClient()
    response = client.fetch_grn(grn_no=grn_no)
    payloads = response.get("data") if isinstance(response, dict) else response

    if isinstance(payloads, dict):
        payload_list = [payloads]
    elif isinstance(payloads, list):
        payload_list = payloads
    else:
        payload_list = []

    return [add_stock_from_grn(payload) for payload in payload_list if isinstance(payload, dict)]


def request_stock(*, item: Item, quantity: Decimal | int | float | str, user) -> StockRequest:
    require_persisted_user(user, field_name="requested_by")
    ensure_item_unit(item)
    quantity = quantize_stock(quantity)
    if quantity <= STOCK_ZERO:
        raise ValidationError({"quantity": "Stock quantity must be greater than zero."})

    return StockRequest.objects.create(
        item=item,
        quantity=quantity,
        requested_by=user,
    )


def approve_stock_request(request_id: int, approver) -> dict[str, Any]:
    from apps.blending.services import add_blending_stock

    require_persisted_user(approver, field_name="approved_by")

    with transaction.atomic():
        stock_request = (
            StockRequest.objects.select_related("item", "requested_by", "approved_by")
            .select_for_update()
            .get(pk=request_id)
        )
        if stock_request.status != StockRequest.Status.PENDING:
            raise ValidationError({"status": "Only pending stock requests can be approved."})

        item = Item.objects.select_for_update().get(pk=stock_request.item_id)
        store_stock = get_store_stock(item.id, item=item, lock_for_update=True)
        if store_stock.quantity < stock_request.quantity:
            raise ValidationError({"quantity": "Insufficient stock in STORE."})

        reference_id = f"REQ-{stock_request.id}"
        store_metadata = {
            "date": timezone.localdate(),
            "ref_id": reference_id,
            "trans_type": "Transfer to blending",
            "contact": TRANSFER_CONTACT,
            "warehouse": STORE_WAREHOUSE,
            "bin": TRANSFER_BIN,
        }
        blending_metadata = {
            "date": timezone.localdate(),
            "ref_id": reference_id,
            "trans_type": "Transfer from store",
            "contact": TRANSFER_CONTACT,
            "warehouse": "BLENDING",
            "bin": TRANSFER_BIN,
        }

        item, store_stock, store_item_transaction = record_store_stock_movement(
            item_id=item.id,
            movement_type="outward",
            quantity=stock_request.quantity,
            metadata=store_metadata,
            locked_item=item,
            locked_store_stock=store_stock,
        )
        blending_stock, blending_item_transaction = add_blending_stock(
            item=item,
            quantity=stock_request.quantity,
            metadata=blending_metadata,
            reference_id=reference_id,
            locked_item=item,
        )

        stock_request.status = StockRequest.Status.APPROVED
        stock_request.approved_by = approver
        stock_request.approved_at = timezone.now()
        stock_request.save(update_fields=["status", "approved_by", "approved_at"])

        store_transaction = StoreTransaction.objects.create(
            item=item,
            transaction_type=StoreTransaction.TransactionType.TRANSFER_OUT,
            quantity=stock_request.quantity,
            reference_id=reference_id,
            metadata={
                "stock_request_id": stock_request.id,
                "requested_by": stock_request.requested_by_id,
                "approved_by": getattr(approver, "id", None),
            },
        )

    return {
        "stock_request": stock_request,
        "store_stock": store_stock,
        "blending_stock": blending_stock,
        "store_transaction": store_transaction,
        "item_transactions": [store_item_transaction, blending_item_transaction],
    }


def reject_stock_request(request_id: int) -> StockRequest:
    with transaction.atomic():
        stock_request = StockRequest.objects.select_for_update().get(pk=request_id)
        if stock_request.status != StockRequest.Status.PENDING:
            raise ValidationError({"status": "Only pending stock requests can be rejected."})

        stock_request.status = StockRequest.Status.REJECTED
        stock_request.approved_by = None
        stock_request.approved_at = None
        stock_request.save(update_fields=["status", "approved_by", "approved_at"])

    return stock_request
