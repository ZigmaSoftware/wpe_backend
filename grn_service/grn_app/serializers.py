from typing import Any

from rest_framework import serializers

from .models import GRN, GRNAuditLog, QCR


class GRNSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRN
        fields = "__all__"

    def validate_grn_no(self, value):
        if not value:
            raise serializers.ValidationError("GRN Number is required")
        return value

    def validate_raw_payload(self, value):
        if value is None or value == "" or value == []:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            import json
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, ValueError):
                raise serializers.ValidationError("raw_payload must be valid JSON if provided.")
        return value


class GRNReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRN
        fields = "__all__"
        db_table = "Purchase_Inwards"

    def to_representation(self, instance):
        raw_payload = instance.raw_payload if isinstance(instance.raw_payload, dict) else {}
        raw_items = raw_payload.get("items")
        item_data = {
            "item_id": instance.item_id,
            "item_serial_number": instance.item_serial_number,
            "product_description": instance.product_description,
            "hsn_code": instance.hsn_code,
            "total_quantity": instance.total_quantity,
            "quantity": instance.quantity,
            "free_quantity": instance.free_quantity,
            "accepted_qty": instance.accepted_qty,
            "rejected_qty": instance.rejected_qty,
            "unit": instance.unit,
            "unit_price": instance.unit_price,
            "total_amount": instance.total_amount,
            "discount": instance.discount,
            "assessable_value": instance.assessable_value,
            "gst_rate": instance.gst_rate,
            "igst_amount": instance.igst_amount,
            "cgst_amount": instance.cgst_amount,
            "sgst_amount": instance.sgst_amount,
            "total_item_value": instance.total_item_value,
        }
        has_item_data = any(value not in (None, "") for value in item_data.values())

        return {
            "id": instance.id,
            "unique_id": instance.unique_id,
            "grn_no": instance.grn_no,
            "grn_date": instance.grn_date,
            "supplier_id": instance.supplier_id,
            "trade_name": instance.trade_name,
            "item_id": instance.item_id,
            "product_description": instance.product_description,
            "req_department": instance.req_department,
            "department": instance.req_department,
            "accepted_qty": instance.accepted_qty,
            "total_after_tax": instance.total_after_tax,
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
            "status": instance.status,
            "process_status": instance.process_status,
            "qc_status": instance.qc_status,
            "moved_to_qcr_at": instance.moved_to_qcr_at,
            "moved_to_qcr_by": instance.moved_to_qcr_by,
            "raw_payload": raw_payload,
            "grn_pending_items": instance.grn_pending_items if isinstance(instance.grn_pending_items, list) else [],
            "document_details": {
                "po_no": instance.po_no,
                "po_date": instance.po_date,
                "grn_no": instance.grn_no,
                "grn_date": instance.grn_date,
                "supplier_invoice_no": instance.supplier_invoice_no,
                "supplier_invoice_date": instance.supplier_invoice_date,
                "gateentry_bookno": instance.gateentry_bookno,
                "gateentry_bookdate": instance.gateentry_bookdate,
                "tolerance": instance.tolerance,
            },
            "document_requirement_details": {
                "req_date": instance.req_date,
                "req_person_name": instance.req_person_name,
                "req_person_id": instance.req_person_id,
                "req_department": instance.req_department,
                "req_reason": instance.req_reason,
            },
            "supplier_details": {
                "supplier_id": instance.supplier_id,
                "gstin": instance.gstin,
                "contact_name": instance.contact_name,
                "trade_name": instance.trade_name,
                "contact_type": instance.contact_type,
                "address1": instance.address1,
                "address2": instance.address2,
                "location": instance.location,
                "pincode": instance.pincode,
                "state_name": instance.state_name,
                "state_code": instance.state_code,
                "country": instance.country,
                "person_name": instance.person_name,
                "phone_number": instance.phone_number,
                "email": instance.email,
                "category": instance.category,
                "segment": instance.segment,
                "sub_segment": instance.sub_segment,
                "sales_contact_id": instance.sales_contact_id,
                "currency": instance.currency,
            },
            "invoice_details": {
                "purchase_bill_no": instance.purchase_bill_no,
                "purchase_bill_date": instance.purchase_bill_date,
                "dc_numbers": instance.dc_numbers,
                "delivery_days_gap": instance.delivery_days_gap,
                "delivery_note_no": instance.delivery_note_no,
                "delivery_note_date": instance.delivery_note_date,
                "order_rating": instance.order_rating,
                "grn_warehouse": instance.grn_warehouse,
                "source_warehouse": instance.source_warehouse,
                "accepted_warehouse": instance.accepted_warehouse,
                "rejected_warehouse": instance.rejected_warehouse,
            },
            "items": raw_items if isinstance(raw_items, list) else ([item_data] if has_item_data else []),
            "value_details": {
                "freight_charge": instance.freight_charge,
                "loading_unloading_charge": instance.loading_unloading_charge,
                "total_before_tax": instance.total_before_tax,
                "total_tax_amount": instance.total_tax_amount,
                "total_after_tax": instance.total_after_tax,
            },
        }


def _serializer_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _serializer_list(value: Any) -> list[dict[str, Any]]:
    return [entry for entry in value if isinstance(entry, dict)] if isinstance(value, list) else []


def _read_qcr_item_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _build_qcr_fallback_item(source_grn: GRN) -> dict[str, Any]:
    return {
        "item_id": source_grn.item_id,
        "item_name": source_grn.product_description or source_grn.item_id,
        "item_code": source_grn.item_id,
        "sent_qty": source_grn.quantity if source_grn.quantity is not None else source_grn.total_quantity,
        "received_qty": source_grn.accepted_qty,
        "accepted_qty": source_grn.accepted_qty,
        "rejected_qty": source_grn.rejected_qty,
        "uom": source_grn.unit,
        "unit": source_grn.unit,
    }


def _build_qcr_record_items(record: QCR) -> list[dict[str, Any]]:
    source_grn = record.source_grn
    source_raw_payload = _serializer_dict(source_grn.raw_payload)
    snapshot = _serializer_dict(record.snapshot)
    snapshot_raw_payload = _serializer_dict(snapshot.get("raw_payload"))

    raw_items = _serializer_list(source_raw_payload.get("items")) or _serializer_list(snapshot_raw_payload.get("items"))
    pending_items = _serializer_list(source_grn.grn_pending_items) or _serializer_list(snapshot.get("grn_pending_items"))
    completed_items = _serializer_list(record.qcr_items)

    if not raw_items and not pending_items and not completed_items and any(
        value not in (None, "") for value in (source_grn.item_id, source_grn.product_description, source_grn.quantity, source_grn.total_quantity)
    ):
        raw_items = [_build_qcr_fallback_item(source_grn)]

    row_count = max(len(raw_items), len(pending_items), len(completed_items))
    rows: list[dict[str, Any]] = []

    for index in range(row_count):
        raw_item = raw_items[index] if index < len(raw_items) else {}
        pending_item = pending_items[index] if index < len(pending_items) else {}
        completed_item = completed_items[index] if index < len(completed_items) else {}

        item_id = _read_qcr_item_value(
            completed_item.get("item_id"),
            pending_item.get("item_id"),
            raw_item.get("item_id"),
        )
        item_name = _read_qcr_item_value(
            completed_item.get("item_name"),
            pending_item.get("item_name"),
            raw_item.get("product_description"),
            raw_item.get("item_name"),
            item_id,
            f"Line {index + 1}",
        )
        item_code = _read_qcr_item_value(
            completed_item.get("item_code"),
            completed_item.get("item_id"),
            pending_item.get("item_code"),
            pending_item.get("item_id"),
            raw_item.get("item_code"),
            raw_item.get("item_id"),
        )
        unit = _read_qcr_item_value(
            completed_item.get("uom"),
            completed_item.get("unit"),
            pending_item.get("uom"),
            pending_item.get("unit"),
            raw_item.get("uom"),
            raw_item.get("unit"),
        )

        rows.append(
            {
                "line_index": _read_qcr_item_value(
                    completed_item.get("line_index"),
                    pending_item.get("line_index"),
                    index,
                ),
                "item_id": item_id,
                "item_name": item_name,
                "item_code": item_code,
                "sent_qty": _read_qcr_item_value(
                    completed_item.get("sent_qty"),
                    pending_item.get("sent_qty"),
                    raw_item.get("quantity"),
                    raw_item.get("total_quantity"),
                ),
                "received_qty": _read_qcr_item_value(
                    completed_item.get("received_qty"),
                    pending_item.get("received_qty"),
                    raw_item.get("received_qty"),
                    raw_item.get("accepted_qty"),
                ),
                "accepted_qty": _read_qcr_item_value(
                    completed_item.get("accepted_qty"),
                    pending_item.get("accepted_qty"),
                    raw_item.get("accepted_qty"),
                ),
                "rejected_qty": _read_qcr_item_value(
                    completed_item.get("rejected_qty"),
                    pending_item.get("rejected_qty"),
                    raw_item.get("rejected_qty"),
                ),
                "rejection_reason": _read_qcr_item_value(
                    completed_item.get("rejection_reason"),
                    pending_item.get("rejection_reason"),
                    raw_item.get("rejection_reason"),
                    "",
                ),
                "uom": unit,
                "unit": unit,
                "store_in_id": _read_qcr_item_value(
                    completed_item.get("store_in_id"),
                    pending_item.get("store_in_id"),
                    raw_item.get("store_in_id"),
                    raw_item.get("store_in"),
                ),
                "store_in_name": _read_qcr_item_value(
                    completed_item.get("store_in_name"),
                    pending_item.get("store_in_name"),
                    raw_item.get("store_in_name"),
                    raw_item.get("store_in"),
                ),
            }
        )

    return rows


class QCRSerializer(serializers.ModelSerializer):
    source_grn_data = GRNReadSerializer(source="source_grn", read_only=True)
    items = serializers.SerializerMethodField()

    class Meta:
        model = QCR
        fields = "__all__"

    def get_items(self, obj: QCR):
        return _build_qcr_record_items(obj)


class GRNAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRNAuditLog
        fields = ["id", "grn_id", "stage", "actor", "notes", "timestamp"]
