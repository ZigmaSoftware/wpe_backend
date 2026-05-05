from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Item, ItemStockTransaction, STOCK_ZERO
from .serializers import ItemSerializer, ItemStockMovementSerializer, ItemStockTransactionSerializer


STOCK_QUANTIZER = Decimal("0.001")
DEFAULT_STOCK_CONTACT = "Manage Stock tool"
DEFAULT_STOCK_BIN = "GEN"
OPENING_STOCK_TRANS_TYPE = "opening stock"
INWARD_TRANS_TYPE = "stock movement inward"
OUTWARD_TRANS_TYPE = "stock movement outward"

STOCK_ANALYSIS_COLUMNS = [
    "S.NO.",
    "Date",
    "Ref ID",
    "Trans Type",
    "Sale Type",
    "Doc ID",
    "Contact",
    "Warehouse",
    "Bin",
    "Inwards",
    "Outwards",
    "Balance",
]

HEADER_ALIASES = {
    "product_type": "product_type",
    "product type": "product_type",
    "item_type": "product_type",
    "item type": "product_type",
    "category": "category",
    "group": "group",
    "sub_group": "sub_group",
    "subgroup": "sub_group",
    "sub group": "sub_group",
    "item_name": "item_name",
    "item name": "item_name",
    "item_code": "item_code",
    "item code": "item_code",
    "hsn_code": "hsn_code",
    "hsn code": "hsn_code",
    "hsn": "hsn_code",
    "unit": "unit",
    "opening_stock": "opening_stock",
    "opening stock": "opening_stock",
    "opening": "opening_stock",
    "current_stock": "current_stock",
    "current stock": "current_stock",
    "on_hand": "current_stock",
    "on hand": "current_stock",
    "stock": "opening_stock",
    "quantity": "quantity",
    "qty": "quantity",
    "incoming_quantity": "incoming_quantity",
    "incoming quantity": "incoming_quantity",
    "weight": "weight",
    "product_details": "product_details",
    "product details": "product_details",
    "description": "description",
    "min_max_status": "min_max_status",
    "min max status": "min_max_status",
    "status": "status",
    "date": "date",
    "stock_date": "date",
    "stock date": "date",
    "ref_id": "ref_id",
    "ref id": "ref_id",
    "reference id": "ref_id",
    "trans_type": "trans_type",
    "trans type": "trans_type",
    "transaction_type": "trans_type",
    "transaction type": "trans_type",
    "sale_type": "sale_type",
    "sale type": "sale_type",
    "doc_id": "doc_id",
    "doc id": "doc_id",
    "document id": "doc_id",
    "contact": "contact",
    "warehouse": "warehouse",
    "bin": "bin",
    "binlot": "bin",
    "bin lot": "bin",
}

REQUIRED_FIELDS = ("category", "group", "sub_group", "item_name", "unit")
BOOLEAN_FIELDS = {"min_max_status", "status"}
DECIMAL_FIELDS = {"opening_stock", "current_stock", "quantity", "incoming_quantity", "weight"}
DATE_FIELDS = {"date"}
TEXT_DEFAULTS = {
    "product_type": "",
    "hsn_code": None,
    "product_details": None,
    "description": None,
    "ref_id": None,
    "trans_type": None,
    "sale_type": None,
    "doc_id": None,
    "contact": None,
    "warehouse": None,
    "bin": None,
}
BOOLEAN_DEFAULTS = {
    "min_max_status": False,
    "status": True,
}
ITEM_MODEL_FIELDS = {
    "product_type",
    "category",
    "group",
    "sub_group",
    "item_name",
    "hsn_code",
    "unit",
    "opening_stock",
    "product_details",
    "description",
    "min_max_status",
    "status",
}
STOCK_QUANTITY_FIELDS = ("incoming_quantity", "quantity", "weight", "opening_stock", "current_stock", "on_hand")
STOCK_METADATA_FIELDS = ("date", "ref_id", "trans_type", "sale_type", "doc_id", "contact", "warehouse", "bin")


def normalize_header(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def is_blank_row(row: tuple[Any, ...]) -> bool:
    for cell in row:
        if cell is None:
            continue
        if isinstance(cell, str) and not cell.strip():
            continue
        return False
    return True


def stringify_cell(value: Any, *, allow_blank: bool = False) -> str | None:
    if value is None:
        return None if allow_blank else ""

    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, int):
        text = str(value)
    elif isinstance(value, float):
        text = str(int(value)) if value.is_integer() else str(value)
    else:
        text = str(value).strip()

    if not text:
        return None if allow_blank else ""

    return text


def clean_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def parse_boolean(value: Any, *, default: bool) -> bool:
    if value is None or value == "":
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(int(value))

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "active", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "inactive", "disabled"}:
        return False

    raise ValueError(f"Cannot interpret boolean value: {value}")


def parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(value, bool):
        return Decimal("1") if value else Decimal("0")

    if isinstance(value, (int, float)):
        return Decimal(str(value))

    normalized = str(value).replace(",", "").strip()
    if not normalized:
        return None

    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Cannot interpret decimal value: {value}") from exc


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    for date_format in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue

    raise ValueError(f"Cannot interpret date value: {value}")


def quantize_stock(value: Any) -> Decimal:
    decimal_value = parse_decimal(value)
    if decimal_value is None:
        return STOCK_ZERO
    return decimal_value.quantize(STOCK_QUANTIZER)


def format_decimal(value: Any) -> str:
    return str(quantize_stock(value))


def format_movement_decimal(value: Any) -> str:
    decimal_value = quantize_stock(value)
    return "" if decimal_value == STOCK_ZERO else str(decimal_value)


def format_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def first_payload_value(field_name: str, *payloads: dict[str, Any]) -> Any:
    for payload in payloads:
        if field_name not in payload:
            continue

        value = payload.get(field_name)
        if value is None or value == "":
            continue
        return value

    return None


def extract_stock_quantity(*payloads: dict[str, Any]) -> Decimal:
    for field_name in STOCK_QUANTITY_FIELDS:
        value = first_payload_value(field_name, *payloads)
        if value is not None:
            return quantize_stock(value)

    return STOCK_ZERO


def extract_stock_metadata(*payloads: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    for field_name in STOCK_METADATA_FIELDS:
        value = first_payload_value(field_name, *payloads)
        if field_name == "date":
            metadata[field_name] = parse_date(value) if value else timezone.localdate()
        else:
            metadata[field_name] = clean_text(value)

    metadata["contact"] = metadata.get("contact") or DEFAULT_STOCK_CONTACT
    metadata["bin"] = metadata.get("bin") or DEFAULT_STOCK_BIN
    return metadata


def item_identity_filter(item_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_name": item_data["item_name"],
        "category": item_data["category"],
        "group": item_data["group"],
        "sub_group": item_data["sub_group"],
        "unit": item_data["unit"],
    }


def item_payload_from_validated_data(validated_data: dict[str, Any], stock_quantity: Decimal) -> dict[str, Any]:
    item_data = {
        field_name: value
        for field_name, value in validated_data.items()
        if field_name in ITEM_MODEL_FIELDS
    }

    if stock_quantity > STOCK_ZERO:
        item_data.setdefault("opening_stock", stock_quantity)

    return item_data


def format_serializer_errors(errors: dict[str, Any]) -> str:
    parts: list[str] = []

    for field, messages in errors.items():
        if isinstance(messages, (list, tuple)):
            message_text = ", ".join(str(message) for message in messages)
        else:
            message_text = str(messages)
        parts.append(f"{field}: {message_text}")

    return "; ".join(parts) if parts else "Invalid item row"


def record_stock_movement(
    *,
    item_id: int,
    movement_type: str,
    quantity: Decimal,
    metadata: dict[str, Any],
    department: str = "STORE",
    locked_item: Item | None = None,
    locked_department_stock: Any | None = None,
) -> tuple[Item, ItemStockTransaction]:
    from apps.blending.services import get_department_stock, normalize_department

    quantity = quantize_stock(quantity)
    if quantity <= STOCK_ZERO:
        raise ValidationError({"quantity": "Stock quantity must be greater than zero."})

    department = normalize_department(department)

    with transaction.atomic():
        item = locked_item or Item.objects.select_for_update().get(pk=item_id)
        department_stock = locked_department_stock or get_department_stock(
            item_id=item.id,
            department=department,
            item=item,
            lock_for_update=True,
        )
        current_stock = quantize_stock(department_stock.quantity)

        if movement_type == "inward":
            inwards = quantity
            outwards = STOCK_ZERO
            balance = current_stock + quantity
        elif movement_type == "outward":
            inwards = STOCK_ZERO
            outwards = quantity
            balance = current_stock - quantity
        else:
            raise ValueError("Invalid stock movement type.")

        if balance < STOCK_ZERO:
            raise ValidationError({"quantity": f"Insufficient stock in {department} department."})

        department_stock.quantity = balance
        department_stock.save(update_fields=["quantity", "updated_at"])

        if department == "STORE":
            item.current_stock = balance
            item.save(update_fields=["current_stock", "updated_at"])

        stock_transaction = ItemStockTransaction.objects.create(
            item=item,
            date=metadata.get("date") or timezone.localdate(),
            ref_id=metadata.get("ref_id"),
            trans_type=metadata.get("trans_type") or (
                INWARD_TRANS_TYPE if movement_type == "inward" else OUTWARD_TRANS_TYPE
            ),
            sale_type=metadata.get("sale_type"),
            doc_id=metadata.get("doc_id"),
            contact=metadata.get("contact") or DEFAULT_STOCK_CONTACT,
            warehouse=metadata.get("warehouse") or department,
            bin=metadata.get("bin") or DEFAULT_STOCK_BIN,
            inwards=inwards,
            outwards=outwards,
            balance=balance,
        )

    return item, stock_transaction


def create_or_update_item_with_stock(
    *,
    validated_data: dict[str, Any],
    raw_payload: dict[str, Any],
    stock_quantity: Decimal | None = None,
) -> tuple[Item, bool, ItemStockTransaction | None]:
    stock_quantity = quantize_stock(stock_quantity if stock_quantity is not None else extract_stock_quantity(raw_payload, validated_data))
    item_data = item_payload_from_validated_data(validated_data, stock_quantity)
    metadata = extract_stock_metadata(raw_payload, validated_data)

    with transaction.atomic():
        existing_item = Item.objects.select_for_update().filter(**item_identity_filter(item_data)).first()

        if existing_item is not None:
            if stock_quantity > STOCK_ZERO:
                metadata["trans_type"] = metadata.get("trans_type") or INWARD_TRANS_TYPE
                item, stock_transaction = record_stock_movement(
                    item_id=existing_item.id,
                    movement_type="inward",
                    quantity=stock_quantity,
                    metadata=metadata,
                )
                return item, False, stock_transaction

            return existing_item, False, None

        item = Item.objects.create(**item_data)

        if stock_quantity > STOCK_ZERO:
            metadata["trans_type"] = metadata.get("trans_type") or OPENING_STOCK_TRANS_TYPE
            item, stock_transaction = record_stock_movement(
                item_id=item.id,
                movement_type="inward",
                quantity=stock_quantity,
                metadata=metadata,
            )
            return item, True, stock_transaction

        return item, True, None


def build_stock_analysis_response(item: Item, transactions) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_inwards = STOCK_ZERO
    total_outwards = STOCK_ZERO

    for index, stock_transaction in enumerate(transactions, start=1):
        total_inwards += quantize_stock(stock_transaction.inwards)
        total_outwards += quantize_stock(stock_transaction.outwards)

        rows.append(
            {
                "S.NO.": index,
                "Date": format_date(stock_transaction.date),
                "Ref ID": stock_transaction.ref_id or "",
                "Trans Type": stock_transaction.trans_type or "",
                "Sale Type": stock_transaction.sale_type or "",
                "Doc ID": stock_transaction.doc_id or "",
                "Contact": stock_transaction.contact or "",
                "Warehouse": stock_transaction.warehouse or "",
                "Bin": stock_transaction.bin or "",
                "Inwards": format_movement_decimal(stock_transaction.inwards),
                "Outwards": format_movement_decimal(stock_transaction.outwards),
                "Balance": format_decimal(stock_transaction.balance),
            }
        )

    return {
        "item_id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "unit": item.unit,
        "opening_stock": format_decimal(item.opening_stock),
        "current_stock": format_decimal(item.current_stock),
        "on_hand": format_decimal(item.current_stock),
        "columns": STOCK_ANALYSIS_COLUMNS,
        "rows": rows,
        "totals": {
            "Inwards": format_decimal(total_inwards),
            "Outwards": format_decimal(total_outwards),
            "Balance": format_decimal(item.current_stock),
        },
    }


class ItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    queryset = Item.objects.all().order_by("-id")
    serializer_class = ItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        product_type = self.request.query_params.get("product_type")
        category = self.request.query_params.get("category")
        group = self.request.query_params.get("group")
        sub_group = self.request.query_params.get("sub_group")

        if product_type:
            queryset = queryset.filter(product_type=product_type)
        if category:
            queryset = queryset.filter(category=category)
        if group:
            queryset = queryset.filter(group=group)
        if sub_group:
            queryset = queryset.filter(sub_group=sub_group)

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            stock_quantity = extract_stock_quantity(request.data, serializer.validated_data)
            item, created, stock_transaction = create_or_update_item_with_stock(
                validated_data=serializer.validated_data,
                raw_payload=request.data,
                stock_quantity=stock_quantity,
            )
        except (IntegrityError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response_data = self.get_serializer(item).data
        response_data["created"] = created
        response_data["stock_updated"] = stock_transaction is not None

        if stock_transaction is not None:
            response_data["stock_transaction"] = ItemStockTransactionSerializer(stock_transaction).data

        if not created:
            response_data["detail"] = (
                "Item already exists. Stock increased."
                if stock_transaction is not None
                else "Item already exists. No duplicate item was created."
            )

        return Response(response_data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def add_inward_stock(self, request, pk=None):
        item = self.get_object()
        serializer = ItemStockMovementSerializer(
            data=request.data,
            context={"movement_type": "inward"},
        )
        serializer.is_valid(raise_exception=True)

        metadata = extract_stock_metadata(request.data, serializer.validated_data)
        metadata["trans_type"] = metadata.get("trans_type") or INWARD_TRANS_TYPE

        item, stock_transaction = record_stock_movement(
            item_id=item.id,
            movement_type="inward",
            quantity=serializer.validated_data["movement_quantity"],
            metadata=metadata,
        )

        return Response(
            {
                "detail": "Inward stock added.",
                "item": self.get_serializer(item).data,
                "stock_transaction": ItemStockTransactionSerializer(stock_transaction).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def add_outward_stock(self, request, pk=None):
        item = self.get_object()
        serializer = ItemStockMovementSerializer(
            data=request.data,
            context={"movement_type": "outward"},
        )
        serializer.is_valid(raise_exception=True)

        metadata = extract_stock_metadata(request.data, serializer.validated_data)
        metadata["trans_type"] = metadata.get("trans_type") or OUTWARD_TRANS_TYPE

        item, stock_transaction = record_stock_movement(
            item_id=item.id,
            movement_type="outward",
            quantity=serializer.validated_data["movement_quantity"],
            metadata=metadata,
        )

        return Response(
            {
                "detail": "Outward stock added.",
                "item": self.get_serializer(item).data,
                "stock_transaction": ItemStockTransactionSerializer(stock_transaction).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def filter_stock_transactions(self, request, item: Item):
        queryset = item.stock_transactions.all().order_by("date", "id")

        ref_id = request.query_params.get("ref_id") or request.query_params.get("transaction_id")
        trans_type = request.query_params.get("trans_type") or request.query_params.get("transaction_type")
        sale_type = request.query_params.get("sale_type")
        doc_id = request.query_params.get("doc_id")
        contact = request.query_params.get("contact")
        warehouse = request.query_params.get("warehouse")
        bin_value = request.query_params.get("bin") or request.query_params.get("binlot")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if ref_id:
            queryset = queryset.filter(ref_id=ref_id)
        if trans_type:
            queryset = queryset.filter(trans_type__icontains=trans_type)
        if sale_type:
            queryset = queryset.filter(sale_type=sale_type)
        if doc_id:
            queryset = queryset.filter(doc_id=doc_id)
        if contact:
            queryset = queryset.filter(contact__icontains=contact)
        if warehouse:
            queryset = queryset.filter(warehouse=warehouse)
        if bin_value:
            queryset = queryset.filter(bin=bin_value)
        if date_from:
            queryset = queryset.filter(date__gte=parse_date(date_from))
        if date_to:
            queryset = queryset.filter(date__lte=parse_date(date_to))

        return queryset

    def stock_analysis(self, request, pk=None):
        item_id = pk or request.query_params.get("item_id")
        if not item_id:
            return Response({"detail": "item_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        item = get_object_or_404(Item, pk=item_id)
        try:
            transactions = self.filter_stock_transactions(request, item)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(build_stock_analysis_response(item, transactions))

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response(
                {"detail": "Please upload an Excel file using the 'file' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not uploaded_file.name.lower().endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
            return Response(
                {"detail": "Only .xlsx Excel files are supported."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            workbook = load_workbook(uploaded_file, data_only=True, read_only=True)
        except Exception:
            return Response(
                {"detail": "The uploaded file is not a valid Excel workbook."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sheet = workbook.active
            header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
            if not header_row:
                return Response(
                    {"detail": "The workbook does not contain a header row."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            column_map: dict[int, str] = {}
            for index, header in enumerate(header_row):
                field_name = HEADER_ALIASES.get(normalize_header(header))
                if field_name and field_name not in column_map.values():
                    column_map[index] = field_name

            missing_required_fields = [field for field in REQUIRED_FIELDS if field not in column_map.values()]
            if missing_required_fields:
                return Response(
                    {
                        "detail": "The workbook is missing required columns: "
                        + ", ".join(missing_required_fields)
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            created_count = 0
            updated_count = 0
            existing_count = 0
            stock_transactions_count = 0
            failed_rows: list[dict[str, Any]] = []
            processed_count = 0

            for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                if is_blank_row(row):
                    continue

                processed_count += 1
                payload: dict[str, Any] = {**TEXT_DEFAULTS, **BOOLEAN_DEFAULTS}

                try:
                    for column_index, field_name in column_map.items():
                        cell_value = row[column_index] if column_index < len(row) else None

                        if field_name in BOOLEAN_FIELDS:
                            payload[field_name] = parse_boolean(cell_value, default=BOOLEAN_DEFAULTS[field_name])
                        elif field_name in DECIMAL_FIELDS:
                            payload[field_name] = parse_decimal(cell_value)
                        elif field_name in DATE_FIELDS:
                            payload[field_name] = parse_date(cell_value)
                        elif field_name in TEXT_DEFAULTS:
                            payload[field_name] = stringify_cell(cell_value, allow_blank=True)
                        else:
                            payload[field_name] = stringify_cell(cell_value)
                except ValueError as exc:
                    failed_rows.append(
                        {
                            "row": row_number,
                            "message": str(exc),
                        }
                    )
                    continue

                stock_quantity = extract_stock_quantity(payload)
                serializer = ItemSerializer(data=payload)
                if not serializer.is_valid():
                    failed_rows.append(
                        {
                            "row": row_number,
                            "message": format_serializer_errors(serializer.errors),
                            "details": serializer.errors,
                        }
                    )
                    continue

                try:
                    item, created, stock_transaction = create_or_update_item_with_stock(
                        validated_data=serializer.validated_data,
                        raw_payload=payload,
                        stock_quantity=stock_quantity,
                    )
                except (IntegrityError, ValueError) as exc:
                    failed_rows.append(
                        {
                            "row": row_number,
                            "message": str(exc),
                        }
                    )
                    continue

                if created:
                    created_count += 1
                elif stock_transaction is not None:
                    updated_count += 1
                else:
                    existing_count += 1

                if stock_transaction is not None:
                    stock_transactions_count += 1

            failed_count = len(failed_rows)
            successful_count = created_count + updated_count + existing_count
            response_body = {
                "created_count": created_count,
                "updated_count": updated_count,
                "existing_count": existing_count,
                "stock_transactions_count": stock_transactions_count,
                "failed_count": failed_count,
                "processed_count": processed_count,
                "errors": failed_rows,
            }

            if successful_count == 0:
                if failed_rows:
                    response_body["detail"] = (
                        f"All rows failed to import. First error: row {failed_rows[0]['row']}: "
                        f"{failed_rows[0]['message']}"
                    )
                else:
                    response_body["detail"] = "The workbook does not contain any item rows."
                return Response(response_body, status=status.HTTP_400_BAD_REQUEST)

            if failed_count > 0:
                return Response(response_body, status=status.HTTP_207_MULTI_STATUS)

            return Response(
                response_body,
                status=status.HTTP_201_CREATED if created_count > 0 else status.HTTP_200_OK,
            )
        finally:
            workbook.close()
