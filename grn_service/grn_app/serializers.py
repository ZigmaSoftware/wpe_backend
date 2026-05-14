from rest_framework import serializers

from .models import GRN, QCR


class GRNSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRN
        fields = "__all__"

    def validate_grn_no(self, value):
        if not value:
            raise serializers.ValidationError("GRN Number is required")
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
            "moved_to_qcr_at": instance.moved_to_qcr_at,
            "moved_to_qcr_by": instance.moved_to_qcr_by,
            "raw_payload": raw_payload,
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
            "items": raw_items if isinstance(raw_items, list) else ([item_data] if has_item_data else []),
            "value_details": {
                "freight_charge": instance.freight_charge,
                "loading_unloading_charge": instance.loading_unloading_charge,
                "total_before_tax": instance.total_before_tax,
                "total_tax_amount": instance.total_tax_amount,
                "total_after_tax": instance.total_after_tax,
            },
        }


class QCRSerializer(serializers.ModelSerializer):
    source_grn_data = GRNSerializer(source="source_grn", read_only=True)

    class Meta:
        model = QCR
        fields = "__all__"
