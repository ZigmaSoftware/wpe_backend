from __future__ import annotations

import re
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import IntegrityError, OperationalError, ProgrammingError, transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import GRN, QCR
from .serializers import GRNReadSerializer, GRNSerializer, QCRSerializer


HEADER_ALIASES = {
    "po_no": "po_no",
    "po number": "po_no",
    "po no": "po_no",
    "po": "po_no",
    "po_date": "po_date",
    "po date": "po_date",
    "grn_no": "grn_no",
    "grn number": "grn_no",
    "grn no": "grn_no",
    "grn": "grn_no",
    "grn_date": "grn_date",
    "grn date": "grn_date",
    "supplier_invoice_no": "supplier_invoice_no",
    "supplier invoice no": "supplier_invoice_no",
    "supplier invoice number": "supplier_invoice_no",
    "supplier_invoice_date": "supplier_invoice_date",
    "supplier invoice date": "supplier_invoice_date",
    "gateentry_bookno": "gateentry_bookno",
    "gate entry book no": "gateentry_bookno",
    "gate entry no": "gateentry_bookno",
    "gateentry_bookdate": "gateentry_bookdate",
    "gate entry book date": "gateentry_bookdate",
    "tolerance": "tolerance",
    "req_date": "req_date",
    "request date": "req_date",
    "req_person_name": "req_person_name",
    "req person name": "req_person_name",
    "req_person_id": "req_person_id",
    "req person id": "req_person_id",
    "req_department": "req_department",
    "req department": "req_department",
    "req_reason": "req_reason",
    "request reason": "req_reason",
    "supplier_id": "supplier_id",
    "supplier id": "supplier_id",
    "gstin": "gstin",
    "contact_name": "contact_name",
    "contact name": "contact_name",
    "trade_name": "trade_name",
    "trade name": "trade_name",
    "contact_type": "contact_type",
    "contact type": "contact_type",
    "address1": "address1",
    "address 1": "address1",
    "address2": "address2",
    "address 2": "address2",
    "location": "location",
    "city": "location",
    "pincode": "pincode",
    "postal code": "pincode",
    "pin code": "pincode",
    "state_name": "state_name",
    "state name": "state_name",
    "state_code": "state_code",
    "state code": "state_code",
    "country": "country",
    "person_name": "person_name",
    "person name": "person_name",
    "phone_number": "phone_number",
    "phone number": "phone_number",
    "phone": "phone_number",
    "email": "email",
    "category": "category",
    "segment": "segment",
    "sub_segment": "sub_segment",
    "sub segment": "sub_segment",
    "sales_contact_id": "sales_contact_id",
    "sales contact id": "sales_contact_id",
    "currency": "currency",
    "item_id": "item_id",
    "item id": "item_id",
    "item_serial_number": "item_serial_number",
    "item serial number": "item_serial_number",
    "product_description": "product_description",
    "product description": "product_description",
    "hsn_code": "hsn_code",
    "hsn code": "hsn_code",
    "total_quantity": "total_quantity",
    "total quantity": "total_quantity",
    "quantity": "quantity",
    "free_quantity": "free_quantity",
    "free quantity": "free_quantity",
    "accepted_qty": "accepted_qty",
    "accepted qty": "accepted_qty",
    "rejected_qty": "rejected_qty",
    "rejected qty": "rejected_qty",
    "unit": "unit",
    "unit_price": "unit_price",
    "unit price": "unit_price",
    "total_amount": "total_amount",
    "total amount": "total_amount",
    "discount": "discount",
    "assessable_value": "assessable_value",
    "assessable value": "assessable_value",
    "gst_rate": "gst_rate",
    "gst rate": "gst_rate",
    "igst_amount": "igst_amount",
    "igst amount": "igst_amount",
    "cgst_amount": "cgst_amount",
    "cgst amount": "cgst_amount",
    "sgst_amount": "sgst_amount",
    "sgst amount": "sgst_amount",
    "total_item_value": "total_item_value",
    "total item value": "total_item_value",
    "freight_charge": "freight_charge",
    "freight charge": "freight_charge",
    "loading_unloading_charge": "loading_unloading_charge",
    "loading unloading charge": "loading_unloading_charge",
    "total_before_tax": "total_before_tax",
    "total before tax": "total_before_tax",
    "total_tax_amount": "total_tax_amount",
    "total tax amount": "total_tax_amount",
    "total_after_tax": "total_after_tax",
    "total after tax": "total_after_tax",
    "status": "status",
}

DATE_FIELDS = {
    "po_date",
    "grn_date",
    "supplier_invoice_date",
    "gateentry_bookdate",
    "req_date",
}

DECIMAL_FIELDS = {
    "total_quantity",
    "quantity",
    "free_quantity",
    "accepted_qty",
    "rejected_qty",
    "unit_price",
    "total_amount",
    "assessable_value",
    "gst_rate",
    "igst_amount",
    "cgst_amount",
    "sgst_amount",
    "total_item_value",
    "freight_charge",
    "total_before_tax",
    "total_tax_amount",
    "total_after_tax",
}

INTEGER_FIELDS = {"item_serial_number"}
BOOLEAN_FIELDS = {"status"}
REQUIRED_FIELDS = ("grn_no",)
RECEIVER_NESTED_KEYS = {"document_details", "document_requirement_details", "supplier_details", "items", "value_details"}
RECEIVER_REQUIRED_FIELDS = (
    "document_details.grn_no",
    "document_details.po_no",
    "document_details.grn_date",
    "supplier_details.supplier_id",
)
MODEL_DATE_FIELDS = {"po_date", "grn_date", "supplier_invoice_date", "gateentry_bookdate"}
GRN_LEGACY_VALUE_FIELDS = (
    "id",
    "po_no",
    "po_date",
    "grn_no",
    "grn_date",
    "supplier_invoice_no",
    "supplier_invoice_date",
    "gateentry_bookno",
    "gateentry_bookdate",
    "tolerance",
    "req_date",
    "req_person_name",
    "req_person_id",
    "req_department",
    "req_reason",
    "supplier_id",
    "gstin",
    "contact_name",
    "trade_name",
    "contact_type",
    "address1",
    "address2",
    "location",
    "pincode",
    "state_name",
    "state_code",
    "country",
    "person_name",
    "phone_number",
    "email",
    "category",
    "segment",
    "sub_segment",
    "sales_contact_id",
    "currency",
    "item_id",
    "item_serial_number",
    "product_description",
    "hsn_code",
    "total_quantity",
    "quantity",
    "free_quantity",
    "accepted_qty",
    "rejected_qty",
    "unit",
    "unit_price",
    "total_amount",
    "discount",
    "assessable_value",
    "gst_rate",
    "igst_amount",
    "cgst_amount",
    "sgst_amount",
    "total_item_value",
    "freight_charge",
    "loading_unloading_charge",
    "total_before_tax",
    "total_tax_amount",
    "total_after_tax",
    "created_at",
    "updated_at",
    "status",
)

ACTIVE_QCR_SCOPES = {"", "active", "qcr", "pending", "open"}
CANCELLED_QCR_SCOPES = {"cancelled", "canceled", "cancel", "rejected", "reject"}
MOVED_TO_GRN_SCOPES = {"moved to grn", "moved_to_grn", "moved-grn", "grn", "approved"}


def resolve_list_scope(request, fallback: str = "") -> str:
    for value in (
        fallback,
        request.query_params.get("tab"),
        request.query_params.get("status"),
        request.query_params.get("view"),
        request.query_params.get("type"),
        request.query_params.get("page"),
        request.query_params.get("scope"),
    ):
        if value is None:
            continue
        normalized = str(value).strip().lower()
        if normalized:
            return normalized
    return ""


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


def parse_boolean(value: Any, *, default: bool = True) -> bool:
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


def parse_integer(value: Any) -> int | None:
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    normalized = str(value).replace(",", "").strip()
    if not normalized:
        return None

    try:
        return int(float(normalized))
    except ValueError as exc:
        raise ValueError(f"Cannot interpret integer value: {value}") from exc


def parse_date(value: Any, *, epoch: Any) -> date | None:
    if value is None or value == "":
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, (int, float)):
        converted = from_excel(value, epoch=epoch)
        return converted.date() if isinstance(converted, datetime) else converted

    normalized = str(value).strip()
    if not normalized:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Cannot interpret date value: {value}")


def format_serializer_errors(errors: dict[str, Any]) -> str:
    parts: list[str] = []

    for field, messages in errors.items():
        if isinstance(messages, (list, tuple)):
            message_text = ", ".join(str(message) for message in messages)
        else:
            message_text = str(messages)
        parts.append(f"{field}: {message_text}")

    return "; ".join(parts) if parts else "Invalid GRN row"


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def get_nested_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def parse_api_date(value: Any) -> date | None:
    if is_blank(value):
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    normalized = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Cannot interpret date value: {value}")


def clean_model_value(field_name: str, value: Any, *, required: bool = False) -> Any:
    if field_name in MODEL_DATE_FIELDS:
        try:
            return parse_api_date(value)
        except ValueError:
            if required:
                raise
            return None

    if field_name in DECIMAL_FIELDS:
        try:
            return parse_decimal(value)
        except ValueError:
            return None

    if field_name in INTEGER_FIELDS:
        try:
            return parse_integer(value)
        except ValueError:
            return None

    return value


def validate_grn_receiver_payload(data: Any) -> dict[str, Any]:
    errors: dict[str, Any] = {}

    if not isinstance(data, dict):
        return {"payload": "Expected a JSON object."}

    document_details = data.get("document_details")
    supplier_details = data.get("supplier_details")
    items = data.get("items")

    if not isinstance(document_details, dict):
        errors["document_details"] = "This object is required."
    if not isinstance(supplier_details, dict):
        errors["supplier_details"] = "This object is required."

    for field_path in RECEIVER_REQUIRED_FIELDS:
        if is_blank(get_nested_value(data, field_path)):
            errors[field_path] = "This field is required."

    if not isinstance(items, list) or not items:
        errors["items"] = "At least one item is required."
    elif not all(isinstance(item, dict) for item in items):
        errors["items"] = "Each item must be an object."

    grn_date = get_nested_value(data, "document_details.grn_date")
    if not is_blank(grn_date):
        try:
            parse_api_date(grn_date)
        except ValueError as exc:
            errors["document_details.grn_date"] = str(exc)

    return errors


def map_nested_grn_payload(data: dict[str, Any]) -> dict[str, Any]:
    document_details = data.get("document_details", {}) or {}
    document_requirement_details = data.get("document_requirement_details", {}) or {}
    supplier_details = data.get("supplier_details", {}) or {}
    items = data.get("items", []) or []
    value_details = data.get("value_details", {}) or {}

    first_item = items[0] if items else {}

    return {
        "po_no": document_details.get("po_no"),
        "po_date": document_details.get("po_date"),
        "grn_no": document_details.get("grn_no"),
        "grn_date": document_details.get("grn_date"),
        "supplier_invoice_no": document_details.get("supplier_invoice_no"),
        "supplier_invoice_date": document_details.get("supplier_invoice_date"),
        "gateentry_bookno": document_details.get("gateentry_bookno"),
        "gateentry_bookdate": document_details.get("gateentry_bookdate"),
        "tolerance": document_details.get("tolerance"),
        "req_date": document_requirement_details.get("req_date"),
        "req_person_name": document_requirement_details.get("req_person_name"),
        "req_person_id": document_requirement_details.get("req_person_id"),
        "req_department": document_requirement_details.get("req_department"),
        "req_reason": document_requirement_details.get("req_reason"),
        "supplier_id": supplier_details.get("supplier_id"),
        "gstin": supplier_details.get("gstin"),
        "contact_name": supplier_details.get("contact_name"),
        "trade_name": supplier_details.get("trade_name"),
        "contact_type": supplier_details.get("contact_type"),
        "address1": supplier_details.get("address1"),
        "address2": supplier_details.get("address2"),
        "location": supplier_details.get("location"),
        "pincode": supplier_details.get("pincode"),
        "state_name": supplier_details.get("state_name"),
        "state_code": supplier_details.get("state_code"),
        "country": supplier_details.get("country"),
        "person_name": supplier_details.get("person_name"),
        "phone_number": supplier_details.get("phone_number"),
        "email": supplier_details.get("email"),
        "category": supplier_details.get("category"),
        "segment": supplier_details.get("segment"),
        "sub_segment": supplier_details.get("sub_segment"),
        "sales_contact_id": supplier_details.get("sales_contact_id"),
        "currency": supplier_details.get("currency"),
        "item_id": first_item.get("item_id"),
        "item_serial_number": first_item.get("item_serial_number"),
        "product_description": first_item.get("product_description"),
        "hsn_code": first_item.get("hsn_code"),
        "total_quantity": first_item.get("total_quantity"),
        "quantity": first_item.get("quantity"),
        "free_quantity": first_item.get("free_quantity"),
        "accepted_qty": first_item.get("accepted_qty"),
        "rejected_qty": first_item.get("rejected_qty"),
        "unit": first_item.get("unit"),
        "unit_price": first_item.get("unit_price"),
        "total_amount": first_item.get("total_amount"),
        "discount": first_item.get("discount"),
        "assessable_value": first_item.get("assessable_value"),
        "gst_rate": first_item.get("gst_rate"),
        "igst_amount": first_item.get("igst_amount"),
        "cgst_amount": first_item.get("cgst_amount"),
        "sgst_amount": first_item.get("sgst_amount"),
        "total_item_value": first_item.get("total_item_value"),
        "freight_charge": value_details.get("freight_charge"),
        "loading_unloading_charge": value_details.get("loading_unloading_charge"),
        "total_before_tax": value_details.get("total_before_tax"),
        "total_tax_amount": value_details.get("total_tax_amount"),
        "total_after_tax": value_details.get("total_after_tax"),
    }


def build_receiver_grn_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = map_nested_grn_payload(data)

    for field_name, value in list(payload.items()):
        payload[field_name] = clean_model_value(
            field_name,
            value,
            required=field_name == "grn_date",
        )

    payload["raw_payload"] = deepcopy(data)
    return payload


def get_actor_name(request) -> str | None:
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        full_name = getattr(user, "get_full_name", lambda: "")()
        username = getattr(user, "get_username", lambda: "")()
        return full_name or username or None

    header_actor = request.headers.get("X-User-Name")
    if header_actor:
        return header_actor.strip() or None

    request_actor = request.data.get("moved_by") if hasattr(request.data, "get") else None
    if request_actor:
        return str(request_actor).strip() or None

    return None


def serialize_grn_snapshot(grn: GRN) -> dict[str, Any]:
    snapshot = model_to_dict(grn, exclude=["id", "created_at", "updated_at"])
    snapshot["id"] = grn.id
    snapshot["created_at"] = grn.created_at.isoformat() if grn.created_at else None
    snapshot["updated_at"] = grn.updated_at.isoformat() if grn.updated_at else None

    for field_name, value in list(snapshot.items()):
        if isinstance(value, Decimal):
            snapshot[field_name] = str(value)
        elif isinstance(value, (date, datetime)):
            snapshot[field_name] = value.isoformat()

    return snapshot


def is_missing_schema_error(exc: Exception) -> bool:
    if not isinstance(exc, (ProgrammingError, OperationalError)):
        return False

    message = str(exc).lower()
    return "doesn't exist" in message or "unknown column" in message or "no such column" in message


def schema_sync_response() -> Response:
    return Response(
        {
            "status": "error",
            "message": "Database schema is not up to date. Apply the latest Purchases_Inwards migration before using the GRN to QCR flow.",
            "code": "schema_out_of_sync",
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def get_compatible_grn_payload() -> list[dict[str, Any]]:
    rows = list(GRN.objects.values(*GRN_LEGACY_VALUE_FIELDS).order_by("-id"))
    for row in rows:
        row["process_status"] = "GRN Process"
        row["moved_to_qcr_at"] = None
        row["moved_to_qcr_by"] = None
    return rows


class GRNAPIViewMixin:
    def get_base_queryset(self, request):
        queryset = GRN.objects.all()
        list_scope = resolve_list_scope(request, getattr(self, "tab_scope", ""))

        if list_scope in MOVED_TO_GRN_SCOPES:
            return queryset.filter(process_status="Moved to GRN")
        if list_scope in ACTIVE_QCR_SCOPES:
            return queryset.filter(status=True, process_status="GRN Process")
        return queryset

    def get_grn_response(self, request):
        try:
            queryset = self.get_base_queryset(request).order_by("-id")

            grn_id = request.query_params.get("id")
            grn_no = request.query_params.get("grn_no")

            if grn_id:
                queryset = queryset.filter(id=grn_id)
            if grn_no:
                queryset = queryset.filter(grn_no=grn_no)

            if (grn_id or grn_no) and not queryset.exists():
                return Response(
                    {
                        "status": "error",
                        "message": "GRN not found",
                        "count": 0,
                        "data": [],
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = GRNReadSerializer(queryset, many=True)
            return Response(
                {
                    "status": "success",
                    "message": "GRN data fetched successfully",
                    "count": queryset.count(),
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except (ProgrammingError, OperationalError) as exc:
            if is_missing_schema_error(exc):
                try:
                    return Response(get_compatible_grn_payload(), status=status.HTTP_200_OK)
                except (ProgrammingError, OperationalError):
                    return schema_sync_response()
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create_grn_response(self, request):
        try:
            data = request.data
            if any(key in data for key in RECEIVER_NESTED_KEYS):
                payload = map_nested_grn_payload(data)
            elif hasattr(data, "dict"):
                payload = data.dict()
            else:
                payload = dict(data)

            serializer = GRNSerializer(data=payload)
            if serializer.is_valid():
                saved_grn = serializer.save()
                return Response(
                    {
                        "status": "success",
                        "message": "GRN stored successfully",
                        "grn_no": saved_grn.grn_no,
                        "grn_id": saved_grn.id,
                    },
                    status=status.HTTP_201_CREATED,
                )

            return Response(
                {
                    "status": "error",
                    "message": "Validation failed",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (ProgrammingError, OperationalError) as exc:
            if is_missing_schema_error(exc):
                return schema_sync_response()
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GRNCreateAPIView(GRNAPIViewMixin, APIView):
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    tab_scope = ""

    def get(self, request):
        return self.get_grn_response(request)

    def post(self, request):
        return self.create_grn_response(request)


class GRNReceiverCreateAPIView(APIView):
    authentication_classes = []
    parser_classes = [JSONParser]
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        grn_no = get_nested_value(data, "document_details.grn_no") if isinstance(data, dict) else None

        if is_blank(grn_no):
            return Response(
                {
                    "status": "error",
                    "message": "Validation failed",
                    "errors": {"document_details.grn_no": "This field is required."},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            grn_no = str(grn_no).strip()
            if GRN.objects.filter(grn_no=grn_no).exists():
                return Response(
                    {"status": "duplicate", "message": "GRN already exists"},
                    status=status.HTTP_200_OK,
                )

            errors = validate_grn_receiver_payload(data)
            if errors:
                return Response(
                    {
                        "status": "error",
                        "message": "Validation failed",
                        "errors": errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            payload = build_receiver_grn_payload(data)
            payload["grn_no"] = grn_no
            serializer = GRNSerializer(data=payload)
            if not serializer.is_valid():
                if GRN.objects.filter(grn_no=grn_no).exists():
                    return Response(
                        {"status": "duplicate", "message": "GRN already exists"},
                        status=status.HTTP_200_OK,
                    )
                return Response(
                    {
                        "status": "error",
                        "message": "Validation failed",
                        "errors": serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                with transaction.atomic():
                    serializer.save()
            except IntegrityError:
                if GRN.objects.filter(grn_no=grn_no).exists():
                    return Response(
                        {"status": "duplicate", "message": "GRN already exists"},
                        status=status.HTTP_200_OK,
                    )
                raise
        except (ProgrammingError, OperationalError) as exc:
            if is_missing_schema_error(exc):
                return schema_sync_response()
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"status": "sent", "message": "GRN received successfully"},
            status=status.HTTP_201_CREATED,
        )


class GRNViewSet(GRNAPIViewMixin, viewsets.ViewSet):
    def list(self, request):
        return self.get_grn_response(request)

    def create(self, request):
        return self.create_grn_response(request)


class GRNImportAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
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
                    {"detail": "The workbook is missing required columns: " + ", ".join(missing_required_fields)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            created_count = 0
            failed_rows: list[dict[str, Any]] = []
            processed_count = 0

            for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                if is_blank_row(row):
                    continue

                processed_count += 1
                payload: dict[str, Any] = {}

                try:
                    for column_index, field_name in column_map.items():
                        cell_value = row[column_index] if column_index < len(row) else None

                        if field_name in DATE_FIELDS:
                            payload[field_name] = parse_date(cell_value, epoch=workbook.epoch)
                        elif field_name in DECIMAL_FIELDS:
                            payload[field_name] = parse_decimal(cell_value)
                        elif field_name in INTEGER_FIELDS:
                            payload[field_name] = parse_integer(cell_value)
                        elif field_name in BOOLEAN_FIELDS:
                            payload[field_name] = parse_boolean(cell_value, default=True)
                        else:
                            payload[field_name] = stringify_cell(cell_value, allow_blank=True)
                except ValueError as exc:
                    failed_rows.append({"row": row_number, "message": str(exc)})
                    continue

                serializer = GRNSerializer(data=payload)
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
                    with transaction.atomic():
                        serializer.save()
                except IntegrityError as exc:
                    failed_rows.append({"row": row_number, "message": str(exc)})
                    continue

                created_count += 1

            failed_count = len(failed_rows)
            response_body = {
                "created_count": created_count,
                "failed_count": failed_count,
                "processed_count": processed_count,
                "errors": failed_rows,
            }

            if created_count == 0:
                if failed_rows:
                    response_body["detail"] = (
                        f"All rows failed to import. First error: row {failed_rows[0]['row']}: "
                        f"{failed_rows[0]['message']}"
                    )
                else:
                    response_body["detail"] = "The workbook does not contain any GRN rows."
                return Response(response_body, status=status.HTTP_400_BAD_REQUEST)

            if failed_count > 0:
                return Response(response_body, status=status.HTTP_207_MULTI_STATUS)

            return Response(response_body, status=status.HTTP_201_CREATED)
        except (ProgrammingError, OperationalError) as exc:
            if is_missing_schema_error(exc):
                return schema_sync_response()
            raise
        finally:
            workbook.close()


class QCRListAPIView(APIView):
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    tab_scope = ""

    def get(self, request):
        try:
            list_scope = resolve_list_scope(request, self.tab_scope)

            queryset = QCR.objects.select_related("source_grn")
            if list_scope in CANCELLED_QCR_SCOPES:
                queryset = queryset.filter(status="Rejected")
            elif list_scope in MOVED_TO_GRN_SCOPES:
                queryset = queryset.filter(status="Moved to GRN")
            elif list_scope == "all":
                queryset = queryset.all()
            else:
                queryset = queryset.filter(status="Active")

            queryset = queryset.order_by("-id")
            serializer = QCRSerializer(queryset, many=True)
            return Response(serializer.data)
        except (ProgrammingError, OperationalError) as exc:
            if is_missing_schema_error(exc):
                return Response([])
            raise


class GRNMoveToQCRAPIView(APIView):
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def post(self, request, pk: int):
        try:
            with transaction.atomic():
                grn = GRN.objects.select_for_update().filter(pk=pk).first()
                if grn is None:
                    return Response(
                        {
                            "status": "error",
                            "message": "The selected GRN record was not found.",
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )

                if QCR.objects.filter(source_grn=grn).exists():
                    return Response(
                        {
                            "status": "error",
                            "message": "This GRN record has already been moved to QCR.",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                moved_at = timezone.now()
                moved_by = get_actor_name(request)
                snapshot = serialize_grn_snapshot(grn)

                qcr_record = QCR.objects.create(
                    source_grn=grn,
                    grn_reference_no=grn.grn_no,
                    snapshot=snapshot,
                    status="Active",
                    moved_to_qcr_at=moved_at,
                    moved_to_qcr_by=moved_by,
                )

                grn.process_status = "Moved to QCR"
                grn.status = False
                grn.moved_to_qcr_at = moved_at
                grn.moved_to_qcr_by = moved_by
                grn.save(update_fields=["process_status", "status", "moved_to_qcr_at", "moved_to_qcr_by", "updated_at"])

            return Response(
                {
                    "status": "success",
                    "message": "GRN record moved to QCR successfully.",
                    "grn": GRNSerializer(grn).data,
                    "qcr": QCRSerializer(qcr_record).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except (ProgrammingError, OperationalError) as exc:
            if is_missing_schema_error(exc):
                return schema_sync_response()
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class QCRStatusUpdateAPIView(APIView):
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def post(self, request, pk: int):
        action = request.data.get("action") if hasattr(request.data, "get") else None
        if action not in {"move_to_grn", "reject"}:
            return Response(
                {
                    "status": "error",
                    "message": "A valid QCR action is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                qcr_record = QCR.objects.select_for_update().select_related("source_grn").filter(pk=pk).first()
                if qcr_record is None:
                    return Response(
                        {
                            "status": "error",
                            "message": "The selected QCR record was not found.",
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )

                if qcr_record.status != "Active":
                    return Response(
                        {
                            "status": "error",
                            "message": "This QCR record has already been processed.",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                grn = qcr_record.source_grn

                if action == "move_to_grn":
                    qcr_record.status = "Moved to GRN"
                    qcr_record.save(update_fields=["status", "updated_at"])
                    grn.process_status = "Moved to GRN"
                    grn.status = True
                    message = "QCR record moved to GRN successfully."
                else:
                    qcr_record.status = "Rejected"
                    qcr_record.save(update_fields=["status", "updated_at"])
                    grn.process_status = "Rejected"
                    grn.status = False
                    message = "QCR record rejected successfully."

                grn.save(update_fields=["process_status", "status", "updated_at"])

            return Response(
                {
                    "status": "success",
                    "message": message,
                    "grn": GRNSerializer(grn).data,
                    "qcr": QCRSerializer(qcr_record).data,
                },
                status=status.HTTP_200_OK,
            )
        except (ProgrammingError, OperationalError) as exc:
            if is_missing_schema_error(exc):
                return schema_sync_response()
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
