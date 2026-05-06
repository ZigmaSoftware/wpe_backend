from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from grn_app.models import GRN, QCR


def build_grn_payload(
    *,
    grn_no: str,
    supplier_id: str,
    trade_name: str,
    product_description: str,
    quantity: str,
    total_after_tax: str,
):
    return {
        "document_details": {
            "po_no": f"PO-{grn_no[-3:]}",
            "po_date": "2026-05-01",
            "grn_no": grn_no,
            "grn_date": "2026-05-05",
            "supplier_invoice_no": f"SUP-{grn_no[-3:]}",
            "supplier_invoice_date": "2026-05-04",
            "gateentry_bookno": f"GE-{grn_no[-3:]}",
            "gateentry_bookdate": "2026-05-05",
            "tolerance": "2%",
        },
        "document_requirement_details": {
            "req_date": "2026-05-03",
            "req_person_name": "Stores Team",
            "req_person_id": "EMP-101",
            "req_department": "Stores",
            "req_reason": "Demo GRN seed data",
        },
        "supplier_details": {
            "supplier_id": supplier_id,
            "gstin": "27ABCDE1234F1Z5",
            "contact_name": trade_name,
            "trade_name": trade_name,
            "contact_type": "Supplier",
            "address1": "Industrial Estate Road",
            "address2": "Unit 5",
            "location": "Pune",
            "pincode": "411019",
            "state_name": "Maharashtra",
            "state_code": "27",
            "country": "India",
            "person_name": "Ravi Kumar",
            "phone_number": "+919999888777",
            "email": "supply@example.com",
            "category": "Raw Material",
            "segment": "Polymer",
            "sub_segment": "Industrial",
            "sales_contact_id": "SC-01",
            "currency": "INR",
        },
        "items": [
            {
                "item_id": "ITM-001",
                "item_serial_number": 1,
                "product_description": product_description,
                "hsn_code": "39012000",
                "total_quantity": quantity,
                "quantity": quantity,
                "free_quantity": "0.00",
                "accepted_qty": quantity,
                "rejected_qty": "0.00",
                "unit": "KG",
                "unit_price": "52.50",
                "total_amount": "10500.00",
                "discount": "0",
                "assessable_value": "10500.00",
                "gst_rate": "18.00",
                "igst_amount": "0.00",
                "cgst_amount": "945.00",
                "sgst_amount": "945.00",
                "total_item_value": total_after_tax,
            },
            {
                "item_id": "ITM-002",
                "item_serial_number": 2,
                "product_description": f"{product_description} - Additive",
                "hsn_code": "38123090",
                "total_quantity": "25.00",
                "quantity": "25.00",
                "free_quantity": "0.00",
                "accepted_qty": "25.00",
                "rejected_qty": "0.00",
                "unit": "KG",
                "unit_price": "40.00",
                "total_amount": "1000.00",
                "discount": "0",
                "assessable_value": "1000.00",
                "gst_rate": "18.00",
                "igst_amount": "0.00",
                "cgst_amount": "90.00",
                "sgst_amount": "90.00",
                "total_item_value": "1180.00",
            },
        ],
        "value_details": {
            "freight_charge": "500.00",
            "loading_unloading_charge": "200.00",
            "total_before_tax": "11700.00",
            "total_tax_amount": "2070.00",
            "total_after_tax": total_after_tax,
        },
    }


class Command(BaseCommand):
    help = "Seed demo GRN and QCR data for the frontend."

    def handle(self, *args, **options):
        with transaction.atomic():
            active_grn = self._upsert_grn(
                grn_no="GRN-2026-001",
                supplier_id="SUP-001",
                trade_name="Greenline Polymers",
                product_description="HDPE Natural Granules",
                quantity="200.00",
                total_after_tax="13770.00",
                process_status="GRN Process",
                status=True,
                moved_to_qcr=False,
            )
            qcr_active_source = self._upsert_grn(
                grn_no="GRN-2026-004",
                supplier_id="SUP-004",
                trade_name="Catalyst Additives",
                product_description="Processing Additive Pack",
                quantity="60.00",
                total_after_tax="5664.00",
                process_status="Moved to QCR",
                status=False,
                moved_to_qcr=True,
            )
            moved_grn = self._upsert_grn(
                grn_no="GRN-2026-002",
                supplier_id="SUP-002",
                trade_name="Wood Fibre House",
                product_description="Wood Flour 80 Mesh",
                quantity="175.00",
                total_after_tax="12540.00",
                process_status="Moved to GRN",
                status=True,
                moved_to_qcr=True,
            )
            rejected_grn = self._upsert_grn(
                grn_no="GRN-2026-003",
                supplier_id="SUP-003",
                trade_name="Additives India",
                product_description="Coupling Agent",
                quantity="50.00",
                total_after_tax="4720.00",
                process_status="Rejected",
                status=False,
                moved_to_qcr=True,
            )

            QCR.objects.filter(source_grn=active_grn).delete()
            self._upsert_qcr(active=False, grn=moved_grn, status="Moved to GRN")
            self._upsert_qcr(active=False, grn=rejected_grn, status="Rejected")
            self._ensure_active_qcr_exists(qcr_active_source)

        self.stdout.write(self.style.SUCCESS("GRN demo data seeded successfully."))

    def _upsert_grn(
        self,
        *,
        grn_no: str,
        supplier_id: str,
        trade_name: str,
        product_description: str,
        quantity: str,
        total_after_tax: str,
        process_status: str,
        status: bool,
        moved_to_qcr: bool,
    ) -> GRN:
        payload = build_grn_payload(
            grn_no=grn_no,
            supplier_id=supplier_id,
            trade_name=trade_name,
            product_description=product_description,
            quantity=quantity,
            total_after_tax=total_after_tax,
        )
        first_item = payload["items"][0]
        moved_at = timezone.now() - timedelta(hours=4) if moved_to_qcr else None

        record, _ = GRN.objects.update_or_create(
            grn_no=grn_no,
            defaults={
                "po_no": payload["document_details"]["po_no"],
                "po_date": payload["document_details"]["po_date"],
                "grn_date": payload["document_details"]["grn_date"],
                "supplier_invoice_no": payload["document_details"]["supplier_invoice_no"],
                "supplier_invoice_date": payload["document_details"]["supplier_invoice_date"],
                "gateentry_bookno": payload["document_details"]["gateentry_bookno"],
                "gateentry_bookdate": payload["document_details"]["gateentry_bookdate"],
                "tolerance": payload["document_details"]["tolerance"],
                "req_date": payload["document_requirement_details"]["req_date"],
                "req_person_name": payload["document_requirement_details"]["req_person_name"],
                "req_person_id": payload["document_requirement_details"]["req_person_id"],
                "req_department": payload["document_requirement_details"]["req_department"],
                "req_reason": payload["document_requirement_details"]["req_reason"],
                "supplier_id": payload["supplier_details"]["supplier_id"],
                "gstin": payload["supplier_details"]["gstin"],
                "contact_name": payload["supplier_details"]["contact_name"],
                "trade_name": payload["supplier_details"]["trade_name"],
                "contact_type": payload["supplier_details"]["contact_type"],
                "address1": payload["supplier_details"]["address1"],
                "address2": payload["supplier_details"]["address2"],
                "location": payload["supplier_details"]["location"],
                "pincode": payload["supplier_details"]["pincode"],
                "state_name": payload["supplier_details"]["state_name"],
                "state_code": payload["supplier_details"]["state_code"],
                "country": payload["supplier_details"]["country"],
                "person_name": payload["supplier_details"]["person_name"],
                "phone_number": payload["supplier_details"]["phone_number"],
                "email": payload["supplier_details"]["email"],
                "category": payload["supplier_details"]["category"],
                "segment": payload["supplier_details"]["segment"],
                "sub_segment": payload["supplier_details"]["sub_segment"],
                "sales_contact_id": payload["supplier_details"]["sales_contact_id"],
                "currency": payload["supplier_details"]["currency"],
                "item_id": first_item["item_id"],
                "item_serial_number": first_item["item_serial_number"],
                "product_description": first_item["product_description"],
                "hsn_code": first_item["hsn_code"],
                "total_quantity": Decimal(str(first_item["total_quantity"])),
                "quantity": Decimal(str(first_item["quantity"])),
                "free_quantity": Decimal(str(first_item["free_quantity"])),
                "accepted_qty": Decimal(str(first_item["accepted_qty"])),
                "rejected_qty": Decimal(str(first_item["rejected_qty"])),
                "unit": first_item["unit"],
                "unit_price": Decimal(str(first_item["unit_price"])),
                "total_amount": Decimal(str(first_item["total_amount"])),
                "discount": first_item["discount"],
                "assessable_value": Decimal(str(first_item["assessable_value"])),
                "gst_rate": Decimal(str(first_item["gst_rate"])),
                "igst_amount": Decimal(str(first_item["igst_amount"])),
                "cgst_amount": Decimal(str(first_item["cgst_amount"])),
                "sgst_amount": Decimal(str(first_item["sgst_amount"])),
                "total_item_value": Decimal(str(first_item["total_item_value"])),
                "freight_charge": Decimal(str(payload["value_details"]["freight_charge"])),
                "loading_unloading_charge": payload["value_details"]["loading_unloading_charge"],
                "total_before_tax": Decimal(str(payload["value_details"]["total_before_tax"])),
                "total_tax_amount": Decimal(str(payload["value_details"]["total_tax_amount"])),
                "total_after_tax": Decimal(str(payload["value_details"]["total_after_tax"])),
                "raw_payload": deepcopy(payload),
                "status": status,
                "process_status": process_status,
                "moved_to_qcr_at": moved_at,
                "moved_to_qcr_by": "admin" if moved_to_qcr else None,
            },
        )
        return record

    def _ensure_active_qcr_exists(self, active_grn: GRN):
        if QCR.objects.filter(source_grn=active_grn).exists():
            active_qcr = QCR.objects.get(source_grn=active_grn)
            active_qcr.status = "Active"
            active_qcr.grn_reference_no = active_grn.grn_no
            active_qcr.snapshot = self._snapshot(active_grn)
            active_qcr.save(update_fields=["status", "grn_reference_no", "snapshot", "updated_at"])
            return

        moved_at = timezone.now() - timedelta(hours=2)
        active_grn.process_status = "Moved to QCR"
        active_grn.status = False
        active_grn.moved_to_qcr_at = moved_at
        active_grn.moved_to_qcr_by = "admin"
        active_grn.save(update_fields=["process_status", "status", "moved_to_qcr_at", "moved_to_qcr_by", "updated_at"])

        QCR.objects.create(
            source_grn=active_grn,
            grn_reference_no=active_grn.grn_no,
            snapshot=self._snapshot(active_grn),
            status="Active",
            moved_to_qcr_at=moved_at,
            moved_to_qcr_by="admin",
        )

    def _upsert_qcr(self, *, active: bool, grn: GRN, status: str):
        moved_at = timezone.now() - timedelta(hours=3)
        record, _ = QCR.objects.update_or_create(
            source_grn=grn,
            defaults={
                "grn_reference_no": grn.grn_no,
                "snapshot": self._snapshot(grn),
                "status": status,
                "moved_to_qcr_at": moved_at,
                "moved_to_qcr_by": "admin",
            },
        )
        if active:
            record.status = "Active"
            record.save(update_fields=["status", "updated_at"])
        return record

    def _snapshot(self, grn: GRN):
        return {
            "grn_no": grn.grn_no,
            "supplier_id": grn.supplier_id,
            "trade_name": grn.trade_name,
            "product_description": grn.product_description,
            "process_status": grn.process_status,
            "total_after_tax": str(grn.total_after_tax) if grn.total_after_tax is not None else None,
        }
