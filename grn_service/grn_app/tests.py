import re
from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.items.models import Item
from apps.store.models import StoreStock, StoreTransaction, Warehouse
from .models import GRN, QCR


MANUAL_GATE_ENTRY_FLAG = "_manual_gate_entry_entry"


@override_settings(INTERNAL_API_KEY="test-internal-key")
class GRNAPIViewTests(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_KEY="test-internal-key")
        self.url = reverse("grn-create")
        self.detail_url = lambda pk: reverse("grn-detail", kwargs={"pk": pk})
        self.receiver_url = reverse("grn-receiver-create")
        self.view_url = reverse("grn-view-list")
        self.import_url = reverse("grn-import")
        self.api_root_url = "/api/grn/"
        self.first_grn = GRN.objects.create(
            grn_no="GRN-001",
            po_no="PO-001",
            supplier_id="SUP-001",
            trade_name="Alpha Supplier",
            item_id="ITEM-001",
            product_description="First Item",
            total_after_tax="118.00",
        )
        self.second_grn = GRN.objects.create(
            grn_no="GRN-002",
            po_no="PO-002",
            supplier_id="SUP-002",
            trade_name="Beta Supplier",
            item_id="ITEM-002",
            product_description="Second Item",
            total_after_tax="236.00",
        )

    def build_receiver_payload(self, grn_no="GRN-RCV-001"):
        return {
            "document_details": {
                "po_no": "PO-RCV-001",
                "po_date": "2026-04-30",
                "grn_no": grn_no,
                "grn_date": "2026-04-30",
                "supplier_invoice_no": "INV-001",
                "supplier_invoice_date": "2026-04-30",
                "gateentry_bookno": "GATE-001",
                "gateentry_bookdate": "2026-04-30",
                "tolerance": "0",
            },
            "document_requirement_details": {
                "req_date": "2026-04-30",
                "req_person_name": "Requester",
                "req_person_id": "REQ-001",
                "req_department": "Purchase",
                "req_reason": "Stock",
            },
            "supplier_details": {
                "supplier_id": "SUP-RCV-001",
                "gstin": "GSTIN001",
                "contact_name": "Supplier Contact",
                "trade_name": "Receiver Supplier",
                "contact_type": "Vendor",
                "address1": "Address 1",
                "address2": "Address 2",
                "location": "Chennai",
                "pincode": "600001",
                "state_name": "Tamil Nadu",
                "state_code": "33",
                "country": "India",
                "person_name": "Supplier Person",
                "phone_number": "9999999999",
                "email": "supplier@example.com",
                "category": "A",
                "segment": "Industrial",
                "sub_segment": "Tools",
                "sales_contact_id": "SC-001",
                "currency": "INR",
            },
            "items": [
                {
                    "item_id": "ITEM-RCV-001",
                    "item_serial_number": 1,
                    "product_description": "Receiver Item 1",
                    "hsn_code": "1234",
                    "total_quantity": "10",
                    "quantity": "10",
                    "free_quantity": 0,
                    "accepted_qty": "10",
                    "rejected_qty": "0",
                    "unit": "NOS",
                    "unit_price": "100",
                    "total_amount": 1000,
                    "discount": "0",
                    "assessable_value": 1000,
                    "gst_rate": "18",
                    "igst_amount": "180",
                    "cgst_amount": "0",
                    "sgst_amount": "0",
                    "total_item_value": "1180",
                },
                {
                    "item_id": "ITEM-RCV-002",
                    "item_serial_number": 2,
                    "product_description": "Receiver Item 2",
                    "hsn_code": "5678",
                    "total_quantity": "5",
                    "quantity": "5",
                    "free_quantity": 0,
                    "accepted_qty": "5",
                    "rejected_qty": "0",
                    "unit": "NOS",
                    "unit_price": "200",
                    "total_amount": 1000,
                    "discount": "0",
                    "assessable_value": 1000,
                    "gst_rate": "18",
                    "igst_amount": "180",
                    "cgst_amount": "0",
                    "sgst_amount": "0",
                    "total_item_value": "1180",
                },
            ],
            "value_details": {
                "freight_charge": "50",
                "loading_unloading_charge": "25",
                "total_before_tax": 2000,
                "total_tax_amount": 360,
                "total_after_tax": 2385,
            },
        }

    def test_get_grn_list_returns_saved_data(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["data"]), 2)
        self.assertEqual(response.data["data"][0]["grn_no"], self.second_grn.grn_no)
        self.assertEqual(
            response.data["data"][0]["document_details"]["po_no"],
            self.second_grn.po_no,
        )
        self.assertEqual(
            response.data["data"][0]["supplier_details"]["trade_name"],
            self.second_grn.trade_name,
        )
        self.assertEqual(
            response.data["data"][0]["items"][0]["product_description"],
            self.second_grn.product_description,
        )
        self.assertEqual(response.data["data"][0]["raw_payload"], {})

    def test_get_grn_list_exposes_flat_department_compatibility_fields(self):
        grn = GRN.objects.create(
            grn_no="GRN-003",
            trade_name="Compat Supplier",
            product_description="Compat Item",
            req_department="Stores",
            accepted_qty="25.00",
        )

        response = self.client.get(self.url, {"grn_no": grn.grn_no})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data["data"][0]
        self.assertEqual(row["req_department"], "Stores")
        self.assertEqual(row["department"], "Stores")
        self.assertEqual(str(row["accepted_qty"]), "25.00")

    def test_get_grn_list_can_filter_by_grn_no(self):
        response = self.client.get(self.url, {"grn_no": self.first_grn.grn_no})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["data"][0]["grn_no"], self.first_grn.grn_no)

    def test_grn_api_root_returns_grn_list(self):
        response = self.client.get(self.api_root_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["count"], 2)

    def test_grn_detail_get_returns_saved_data(self):
        response = self.client.get(self.detail_url(self.first_grn.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["data"]["id"], self.first_grn.id)
        self.assertEqual(response.data["data"]["grn_no"], self.first_grn.grn_no)
        self.assertEqual(
            response.data["data"]["document_details"]["po_no"],
            self.first_grn.po_no,
        )

    def test_grn_viewset_get_returns_saved_data(self):
        response = self.client.get(self.view_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["count"], 2)

    def test_grn_viewset_post_creates_grn(self):
        payload = {
            "document_details": {
                "grn_no": "GRN-003",
            }
        }

        response = self.client.post(self.view_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["grn_no"], "GRN-003")
        self.assertTrue(GRN.objects.filter(grn_no="GRN-003").exists())

    def test_grn_detail_patch_updates_only_allowed_nested_fields(self):
        payload = self.build_receiver_payload("GRN-EDIT-001")
        grn = GRN.objects.create(
            grn_no="GRN-EDIT-001",
            po_no="PO-RCV-001",
            po_date=date(2026, 4, 30),
            grn_date=date(2026, 4, 30),
            supplier_invoice_no="INV-001",
            supplier_invoice_date=date(2026, 4, 30),
            gateentry_bookno="GATE-001",
            gateentry_bookdate=date(2026, 4, 30),
            tolerance="0",
            req_date="2026-04-30",
            req_person_name="Requester",
            req_person_id="REQ-001",
            req_department="Purchase",
            req_reason="Stock",
            supplier_id="SUP-RCV-001",
            trade_name="Receiver Supplier",
            item_id="ITEM-RCV-001",
            item_serial_number=1,
            product_description="Receiver Item 1",
            accepted_qty="10.00",
            rejected_qty="0.00",
            free_quantity="0.00",
            raw_payload=payload,
        )

        response = self.client.patch(
            self.detail_url(grn.id),
            {
                "document_details": {
                    "po_no": "PO-ATTEMPTED-CHANGE",
                    "gateentry_bookno": "GATE-EDIT-100",
                    "gateentry_bookdate": "2026-05-02",
                    "tolerance": "2",
                },
                "document_requirement_details": {
                    "req_department": "Stores",
                    "req_reason": "Physical inward correction",
                },
                "supplier_details": {
                    "trade_name": "Attempted Supplier Change",
                },
                "items": [
                    {
                        "item_id": "ITEM-ATTEMPTED-CHANGE",
                        "item_serial_number": 3,
                        "accepted_qty": "8.50",
                        "rejected_qty": "1.50",
                    },
                    {
                        "accepted_qty": "4.00",
                        "rejected_qty": "1.00",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["data"]["document_details"]["gateentry_bookno"], "GATE-EDIT-100")
        self.assertEqual(response.data["data"]["document_requirement_details"]["req_department"], "Stores")
        self.assertEqual(response.data["data"]["items"][0]["accepted_qty"], "8.50")
        self.assertEqual(response.data["data"]["items"][1]["accepted_qty"], "4.00")

        grn.refresh_from_db()
        self.assertEqual(grn.po_no, "PO-RCV-001")
        self.assertEqual(grn.gateentry_bookno, "GATE-EDIT-100")
        self.assertEqual(str(grn.gateentry_bookdate), "2026-05-02")
        self.assertEqual(grn.req_department, "Stores")
        self.assertEqual(grn.req_reason, "Physical inward correction")
        self.assertEqual(grn.trade_name, "Receiver Supplier")
        self.assertEqual(grn.item_id, "ITEM-RCV-001")
        self.assertEqual(grn.item_serial_number, 3)
        self.assertEqual(str(grn.accepted_qty), "8.50")
        self.assertEqual(str(grn.rejected_qty), "1.50")
        self.assertEqual(grn.raw_payload["document_details"]["po_no"], "PO-RCV-001")
        self.assertEqual(grn.raw_payload["document_details"]["gateentry_bookno"], "GATE-EDIT-100")
        self.assertTrue(grn.raw_payload["document_details"][MANUAL_GATE_ENTRY_FLAG])
        self.assertEqual(grn.raw_payload["supplier_details"]["trade_name"], "Receiver Supplier")
        self.assertEqual(grn.raw_payload["items"][0]["item_id"], "ITEM-RCV-001")
        self.assertEqual(grn.raw_payload["items"][0]["item_serial_number"], 3)
        self.assertEqual(grn.raw_payload["items"][1]["accepted_qty"], "4.00")

    def test_grn_detail_patch_rejects_inactive_records(self):
        grn = GRN.objects.create(
            grn_no="GRN-EDIT-LOCKED",
            status=False,
            process_status="Moved to QCR",
        )

        response = self.client.patch(
            self.detail_url(grn.id),
            {
                "document_requirement_details": {
                    "req_department": "Stores",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["status"], "error")
        self.assertIn("Gate Entry stage", response.data["message"])

    def test_grn_detail_patch_requires_gate_entry_book_fields(self):
        payload = self.build_receiver_payload("GRN-EDIT-REQ-001")
        grn = GRN.objects.create(
            grn_no="GRN-EDIT-REQ-001",
            po_no="PO-RCV-001",
            grn_date=date(2026, 4, 30),
            gateentry_bookno="GATE-001",
            gateentry_bookdate=date(2026, 4, 30),
            raw_payload=payload,
        )

        response = self.client.patch(
            self.detail_url(grn.id),
            {
                "document_details": {
                    "gateentry_bookno": "",
                    "gateentry_bookdate": "",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["message"], "Validation failed")
        self.assertEqual(
            response.data["errors"],
            {
                "document_details": {
                    "gateentry_bookno": ["Gate Entry Book No is required."],
                    "gateentry_bookdate": ["Gate Entry Book Date is required."],
                }
            },
        )

    def test_grn_receiver_creates_grn_from_sender_payload(self):
        payload = self.build_receiver_payload()
        response = self.client.post(
            self.receiver_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=payload["document_details"]["grn_no"],
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response["Content-Type"].startswith("application/json"))

        grn = GRN.objects.get(grn_no="GRN-RCV-001")
        self.assertEqual(
            response.data,
            {
                "status": "sent",
                "message": "GRN received and processed successfully.",
                "response_code": f"WPE-GRN-{grn.id:06d}",
                "grn_no": grn.grn_no,
                "receiver_reference": grn.unique_id,
                "received_at": timezone.localtime(grn.created_at).isoformat(),
                "errors": None,
            },
        )
        self.assertEqual(grn.po_no, "PO-RCV-001")
        self.assertEqual(grn.supplier_id, "SUP-RCV-001")
        self.assertEqual(grn.item_id, "ITEM-RCV-001")
        self.assertEqual(grn.raw_payload["items"][1]["item_id"], "ITEM-RCV-002")
        self.assertTrue(re.fullmatch(r"WPE-\d{8}", grn.unique_id))
        self.assertEqual(Item.objects.filter(external_item_id__in=["ITEM-RCV-001", "ITEM-RCV-002"]).count(), 0)
        self.assertEqual(StoreStock.objects.count(), 0)
        self.assertEqual(StoreTransaction.objects.count(), 0)

    def test_grn_receiver_duplicate_returns_200_without_creating_duplicate(self):
        payload = self.build_receiver_payload("GRN-RCV-DUP")

        first_response = self.client.post(self.receiver_url, payload, format="json")
        duplicate_response = self.client.post(self.receiver_url, payload, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate_response.status_code, status.HTTP_200_OK)
        grn = GRN.objects.get(grn_no="GRN-RCV-DUP")
        self.assertEqual(
            duplicate_response.data,
            {
                "status": "duplicate",
                "message": "GRN already exists.",
                "response_code": f"WPE-GRN-{grn.id:06d}",
                "grn_no": grn.grn_no,
                "receiver_reference": grn.unique_id,
                "received_at": timezone.localtime(grn.created_at).isoformat(),
                "errors": None,
            },
        )
        self.assertEqual(GRN.objects.filter(grn_no="GRN-RCV-DUP").count(), 1)
        self.assertEqual(Item.objects.filter(external_item_id__in=["ITEM-RCV-001", "ITEM-RCV-002"]).count(), 0)
        self.assertEqual(StoreStock.objects.count(), 0)
        self.assertEqual(StoreTransaction.objects.count(), 0)

    def test_grn_receiver_invalid_payload_returns_400(self):
        payload = self.build_receiver_payload("GRN-RCV-BAD")
        payload["document_details"]["po_no"] = ""
        payload["items"] = []

        response = self.client.post(self.receiver_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response["Content-Type"].startswith("application/json"))
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["message"], "Payload validation failed.")
        self.assertEqual(response.data["response_code"], "WPE-VAL-000400")
        self.assertEqual(response.data["grn_no"], "GRN-RCV-BAD")
        self.assertIsNone(response.data["receiver_reference"])
        self.assertIsNotNone(response.data["received_at"])
        self.assertEqual(
            response.data["errors"],
            {
                "po_no": ["This field is required."],
                "items": ["At least one item is required."],
            },
        )
        self.assertFalse(GRN.objects.filter(grn_no="GRN-RCV-BAD").exists())

    def test_grn_receiver_duplicate_can_be_detected_from_idempotency_key(self):
        payload = self.build_receiver_payload("GRN-RCV-KEY-001")

        first_response = self.client.post(
            self.receiver_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="GRN-RCV-KEY-001",
        )

        duplicate_payload = self.build_receiver_payload("GRN-RCV-KEY-002")
        duplicate_response = self.client.post(
            self.receiver_url,
            duplicate_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="GRN-RCV-KEY-001",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(GRN.objects.count(), 3)
        self.assertFalse(GRN.objects.filter(grn_no="GRN-RCV-KEY-002").exists())

        grn = GRN.objects.get(grn_no="GRN-RCV-KEY-001")
        self.assertEqual(
            duplicate_response.data,
            {
                "status": "duplicate",
                "message": "GRN already exists.",
                "response_code": f"WPE-GRN-{grn.id:06d}",
                "grn_no": "GRN-RCV-KEY-002",
                "receiver_reference": grn.unique_id,
                "received_at": timezone.localtime(grn.created_at).isoformat(),
                "errors": None,
            },
        )

    def test_grn_receiver_does_not_touch_store_items_before_qcr_move(self):
        existing_item = Item.objects.create(
            category="GRN Imported",
            group="Inbound GRN",
            sub_group="Auto Created",
            item_name="Receiver Item 1",
            unit="NOS",
            opening_stock="0.000",
            current_stock="0.000",
        )
        payload = self.build_receiver_payload("GRN-RCV-EXISTING")

        response = self.client.post(self.receiver_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        existing_item.refresh_from_db()
        self.assertIsNone(existing_item.external_item_id)
        self.assertEqual(str(existing_item.current_stock), "0.000")
        self.assertEqual(Item.objects.filter(item_name="Receiver Item 1").count(), 1)
        self.assertEqual(Item.objects.filter(external_item_id="ITEM-RCV-002").count(), 0)
        self.assertEqual(StoreStock.objects.count(), 0)
        self.assertEqual(StoreTransaction.objects.count(), 0)

    def test_grn_receiver_does_not_validate_store_item_resolution_before_qcr_move(self):
        Item.objects.create(
            category="GRN Imported",
            group="Inbound GRN",
            sub_group="Auto Created",
            item_name="Existing External Match",
            external_item_id="ITEM-RCV-001",
            unit="NOS",
            opening_stock="0.000",
            current_stock="0.000",
        )
        Item.objects.create(
            category="GRN Imported",
            group="Inbound GRN",
            sub_group="Auto Created",
            item_name="Receiver Item 1",
            unit="NOS",
            opening_stock="0.000",
            current_stock="0.000",
        )
        payload = self.build_receiver_payload("GRN-RCV-CONFLICT")

        response = self.client.post(self.receiver_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "sent")
        self.assertTrue(GRN.objects.filter(grn_no="GRN-RCV-CONFLICT").exists())
        self.assertEqual(StoreStock.objects.count(), 0)
        self.assertEqual(StoreTransaction.objects.count(), 0)

    def test_grn_receiver_invalid_json_returns_structured_400(self):
        response = self.client.generic(
            "POST",
            self.receiver_url,
            "{bad json",
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="GRN-RCV-PARSE",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response["Content-Type"].startswith("application/json"))
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["message"], "Payload validation failed.")
        self.assertEqual(response.data["response_code"], "WPE-VAL-000400")
        self.assertEqual(response.data["grn_no"], "GRN-RCV-PARSE")
        self.assertIsNone(response.data["receiver_reference"])
        self.assertIn("payload", response.data["errors"])

    def test_grn_receiver_internal_error_returns_structured_500(self):
        payload = self.build_receiver_payload("GRN-RCV-ERR")

        with patch("grn_app.views.GRNSerializer.save", side_effect=RuntimeError("boom")):
            response = self.client.post(self.receiver_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertTrue(response["Content-Type"].startswith("application/json"))
        self.assertEqual(
            response.data,
            {
                "status": "error",
                "message": "Internal processing failed.",
                "response_code": "WPE-ERR-000500",
                "grn_no": "GRN-RCV-ERR",
                "receiver_reference": None,
                "received_at": response.data["received_at"],
                "errors": {"non_field_errors": ["Unexpected server error."]},
            },
        )
        self.assertFalse(GRN.objects.filter(grn_no="GRN-RCV-ERR").exists())

    def test_get_grn_list_returns_not_found_for_missing_grn(self):
        response = self.client.get(self.url, {"grn_no": "GRN-404"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["count"], 0)

    def test_grn_import_accepts_excel_date_cell_for_req_date(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["grn_no", "grn_date", "req_date"])
        sheet.append(["GRN-IMPORT-001", date(2026, 5, 1), date(2026, 4, 30)])

        file_buffer = BytesIO()
        workbook.save(file_buffer)
        upload = SimpleUploadedFile(
            "grn-import.xlsx",
            file_buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response = self.client.post(self.import_url, {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created_count"], 1)

        grn = GRN.objects.get(grn_no="GRN-IMPORT-001")
        self.assertEqual(str(grn.grn_date), "2026-05-01")
        self.assertEqual(grn.req_date, "2026-04-30")

    def test_grn_import_groups_same_grn_number_rows_into_single_record_with_multiple_items(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append([
            "grn_no",
            "grn_date",
            "supplier_id",
            "trade_name",
            "item_id",
            "item_serial_number",
            "product_description",
            "total_quantity",
            "quantity",
            "accepted_qty",
            "rejected_qty",
            "unit",
            "total_amount",
            "igst_amount",
            "cgst_amount",
            "sgst_amount",
            "total_item_value",
            "total_after_tax",
        ])
        sheet.append([
            "GRN-MULTI-001",
            date(2026, 5, 1),
            "SUP-MULTI-001",
            "Grouped Supplier",
            "ITEM-MULTI-001",
            1,
            "Grouped Item 1",
            10,
            10,
            10,
            0,
            "NOS",
            1000,
            180,
            0,
            0,
            1180,
            1180,
        ])
        sheet.append([
            "GRN-MULTI-001",
            date(2026, 5, 1),
            "SUP-MULTI-001",
            "Grouped Supplier",
            "ITEM-MULTI-002",
            2,
            "Grouped Item 2",
            5,
            5,
            5,
            0,
            "NOS",
            1000,
            180,
            0,
            0,
            1180,
            1180,
        ])

        file_buffer = BytesIO()
        workbook.save(file_buffer)
        upload = SimpleUploadedFile(
            "grn-import-multi.xlsx",
            file_buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response = self.client.post(self.import_url, {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["processed_count"], 2)
        self.assertEqual(response.data["created_count"], 1)

        grn = GRN.objects.get(grn_no="GRN-MULTI-001")
        self.assertEqual(grn.trade_name, "Grouped Supplier")
        self.assertEqual(str(grn.total_quantity), "15.00")
        self.assertEqual(str(grn.accepted_qty), "15.00")
        self.assertEqual(str(grn.total_after_tax), "2360.00")
        self.assertEqual(len(grn.raw_payload["items"]), 2)
        self.assertEqual(grn.raw_payload["items"][0]["item_id"], "ITEM-MULTI-001")
        self.assertEqual(grn.raw_payload["items"][1]["item_id"], "ITEM-MULTI-002")
        self.assertEqual(grn.raw_payload["items"][1]["product_description"], "Grouped Item 2")


@override_settings(INTERNAL_API_KEY="test-internal-key")
class GRNQCRFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY="test-internal-key")

    def ensure_qcr_workflow_warehouses(self):
        qc_pending, _ = Warehouse.objects.get_or_create(
            code="QC_PENDING_CBE",
            defaults={
                "name": "QC Pending Warehouse - CBE",
                "warehouse_type": Warehouse.WarehouseType.QC_PENDING,
                "is_active": True,
                "is_system": True,
            },
        )
        store, _ = Warehouse.objects.get_or_create(
            code="STORE",
            defaults={
                "name": "Main Store",
                "warehouse_type": Warehouse.WarehouseType.STORE,
                "is_active": True,
                "is_system": True,
            },
        )
        rejected, _ = Warehouse.objects.get_or_create(
            code="REJECTED_CBE",
            defaults={
                "name": "Rejected Warehouse - CBE",
                "warehouse_type": Warehouse.WarehouseType.REJECTED,
                "is_active": True,
                "is_system": True,
            },
        )
        return qc_pending, store, rejected

    def create_active_qcr_record(self, *, grn_no="GRN-QCR-001"):
        qc_pending, _store, _rejected = self.ensure_qcr_workflow_warehouses()
        raw_payload = {
            "document_details": {
                "grn_no": grn_no,
                "grn_date": "2026-05-05",
            },
            "supplier_details": {
                "trade_name": "Acme Polymers",
            },
            "items": [
                {
                    "item_id": f"{grn_no}-ITEM-1",
                    "product_description": "QCR Line Item 1",
                    "quantity": "10.000",
                    "received_qty": "9",
                    "accepted_qty": "9",
                    "rejected_qty": "1",
                    "unit": "kg",
                    "store_in_id": str(qc_pending.id),
                    "store_in_name": qc_pending.name,
                },
                {
                    "item_id": f"{grn_no}-ITEM-2",
                    "product_description": "QCR Line Item 2",
                    "quantity": "5.000",
                    "received_qty": "5",
                    "accepted_qty": "5",
                    "rejected_qty": "0",
                    "unit": "kg",
                    "store_in_id": str(qc_pending.id),
                    "store_in_name": qc_pending.name,
                },
            ],
        }
        pending_items = [
            {
                "line_index": 0,
                "item_id": f"{grn_no}-ITEM-1",
                "item_name": "QCR Line Item 1",
                "unit": "kg",
                "sent_qty": "10.000",
                "received_qty": "9",
                "store_in_id": str(qc_pending.id),
                "store_in_name": qc_pending.name,
            },
            {
                "line_index": 1,
                "item_id": f"{grn_no}-ITEM-2",
                "item_name": "QCR Line Item 2",
                "unit": "kg",
                "sent_qty": "5.000",
                "received_qty": "5",
                "store_in_id": str(qc_pending.id),
                "store_in_name": qc_pending.name,
            },
        ]
        first_item = Item.objects.create(
            category="GRN Imported",
            group="Inbound GRN",
            sub_group="Auto Created",
            item_name="QCR Line Item 1",
            external_item_id=f"{grn_no}-ITEM-1",
            unit="kg",
            opening_stock="0.000",
            current_stock="0.000",
        )
        second_item = Item.objects.create(
            category="GRN Imported",
            group="Inbound GRN",
            sub_group="Auto Created",
            item_name="QCR Line Item 2",
            external_item_id=f"{grn_no}-ITEM-2",
            unit="kg",
            opening_stock="0.000",
            current_stock="0.000",
        )
        StoreStock.objects.create(item=first_item, warehouse=qc_pending, available_qty="9.000", reserved_qty="0.000")
        StoreStock.objects.create(item=second_item, warehouse=qc_pending, available_qty="5.000", reserved_qty="0.000")
        grn = GRN.objects.create(
            grn_no=grn_no,
            grn_date=date(2026, 5, 5),
            trade_name="Acme Polymers",
            item_id=f"{grn_no}-ITEM-1",
            product_description="QCR Line Item 1",
            accepted_qty="14.00",
            rejected_qty="1.00",
            unit="kg",
            raw_payload=raw_payload,
            grn_pending_items=pending_items,
            status=False,
            process_status=GRN.PROCESS_STATUS_QCR,
        )
        qcr = QCR.objects.create(
            source_grn=grn,
            grn_reference_no=grn.grn_no,
            snapshot={
                "grn_no": grn.grn_no,
                "raw_payload": raw_payload,
                "grn_pending_items": pending_items,
            },
            status="Active",
            moved_to_qcr_at=grn.created_at,
        )
        return grn, qcr

    def test_gate_entry_move_routes_record_to_qcr_and_generates_grn_no(self):
        grn = GRN.objects.create(
            grn_no="GRN-101",
            trade_name="Acme Polymers",
            item_id="ITEM-101",
            product_description="Gate Entry Item",
            unit="kg",
            gateentry_bookno="GATE-101",
            gateentry_bookdate=date(2026, 5, 1),
            raw_payload={
                "document_details": {MANUAL_GATE_ENTRY_FLAG: True},
                "supplier_details": {"trade_name": "Acme Polymers"},
                "items": [
                    {"item_id": "ITEM-101", "product_description": "Gate Entry Item", "quantity": "10.000", "unit": "kg"},
                ],
            },
        )

        move_response = self.client.post(
            f"/api/grn/{grn.id}/move-to-qcr/",
            {"items": [{"received_qty": "9"}]},
            format="json",
        )

        self.assertEqual(move_response.status_code, 201)

        grn.refresh_from_db()
        qcr = QCR.objects.get(source_grn=grn)
        self.assertFalse(grn.status)
        self.assertEqual(grn.process_status, GRN.PROCESS_STATUS_QCR)
        self.assertEqual(qcr.generated_grn_no, "GRN - WPE - 0001")

        list_response = self.client.get("/api/grn/")
        pending_response = self.client.get("/api/grn/pending/")
        qcr_response = self.client.get("/api/qcr/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["data"], [])
        self.assertEqual(pending_response.status_code, 200)
        self.assertEqual(pending_response.json()["data"], [])
        self.assertEqual(qcr_response.status_code, 200)
        self.assertEqual(len(qcr_response.json()), 1)

    def test_move_to_qcr_requires_gate_entry_book_fields(self):
        grn = GRN.objects.create(grn_no="GRN-101-BLANK")

        move_response = self.client.post(f"/api/grn/{grn.id}/move-to-qcr/", {"items": [{"received_qty": "1"}]}, format="json")

        self.assertEqual(move_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(move_response.data["status"], "error")
        self.assertEqual(
            move_response.data["errors"],
            {
                "gateentry_bookno": "Gate Entry Book No is required before moving to QCR.",
                "gateentry_bookdate": "Gate Entry Book Date is required before moving to QCR.",
            },
        )

    def test_move_to_qcr_requires_manual_gate_entry_confirmation(self):
        grn = GRN.objects.create(
            grn_no="GRN-101-AUTO",
            gateentry_bookno="GATE-101-AUTO",
            gateentry_bookdate=date(2026, 5, 1),
            raw_payload={"document_details": {"gateentry_bookno": "GATE-101-AUTO", "gateentry_bookdate": "2026-05-01"}},
        )

        move_response = self.client.post(f"/api/grn/{grn.id}/move-to-qcr/", {}, format="json")

        self.assertEqual(move_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            move_response.data["errors"],
            {
                "gateentry_bookno": "Gate Entry Book No must be entered manually before moving to QCR.",
                "gateentry_bookdate": "Gate Entry Book Date must be entered manually before moving to QCR.",
            },
        )

    def test_grn_pending_move_to_qcr_requires_complete_item_rows(self):
        grn = GRN.objects.create(
            grn_no="GRN-101-PENDING",
            process_status=GRN.PROCESS_STATUS_GRN_PENDING,
            raw_payload={
                "items": [
                    {"item_id": "ITEM-1", "product_description": "Pending Item 1", "quantity": "10.000"},
                    {"item_id": "ITEM-2", "product_description": "Pending Item 2", "quantity": "5.000"},
                ]
            },
        )

        response = self.client.post(
            f"/api/grn/{grn.id}/move-pending-to-qcr/",
            {
                "items": [
                    {"received_qty": "9", "store_in_id": "1", "store_in_name": "Main Store"},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["status"], "error")
        self.assertIn("items", response.data["errors"])

    def test_grn_pending_move_to_qcr_creates_qcr_and_updates_quantities(self):
        grn = GRN.objects.create(
            grn_no="GRN-101-TO-QCR",
            trade_name="Acme Polymers",
            item_id="ITEM-1",
            product_description="Pending Item 1",
            process_status=GRN.PROCESS_STATUS_GRN_PENDING,
            raw_payload={
                "supplier_details": {"trade_name": "Acme Polymers"},
                "items": [
                    {"item_id": "ITEM-1", "product_description": "Pending Item 1", "quantity": "10.000", "unit": "kg"},
                    {"item_id": "ITEM-2", "product_description": "Pending Item 2", "quantity": "5.000", "unit": "kg"},
                ],
            },
        )

        response = self.client.post(
            f"/api/grn/{grn.id}/move-pending-to-qcr/",
            {
                "items": [
                    {"received_qty": "9", "store_in_id": "1", "store_in_name": "Main Store"},
                    {"received_qty": "5", "store_in_id": "2", "store_in_name": "QC Rack"},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        grn.refresh_from_db()
        qcr = QCR.objects.get(source_grn=grn)

        self.assertEqual(grn.process_status, GRN.PROCESS_STATUS_QCR)
        self.assertFalse(grn.status)
        self.assertEqual(str(grn.accepted_qty), "14.00")
        self.assertEqual(str(grn.rejected_qty), "0.00")
        self.assertEqual(grn.raw_payload["items"][0]["accepted_qty"], "9")
        self.assertEqual(grn.raw_payload["items"][0]["rejected_qty"], "0")
        self.assertEqual(grn.raw_payload["items"][0]["store_in_name"], "Main Store")
        self.assertEqual(grn.raw_payload["items"][1]["accepted_qty"], "5")
        self.assertEqual(qcr.status, "Active")
        self.assertEqual(qcr.generated_grn_no, "GRN - WPE - 0001")

        pending_response = self.client.get("/api/grn/pending/")
        qcr_response = self.client.get("/api/qcr/")

        self.assertEqual(pending_response.status_code, 200)
        self.assertEqual(pending_response.json()["data"], [])
        self.assertEqual(qcr_response.status_code, 200)
        self.assertEqual(len(qcr_response.json()), 1)

    def test_gate_entry_move_to_qcr_adopts_source_unit_for_unused_item_code(self):
        existing_item = Item.objects.create(
            category="GRN Imported",
            group="Inbound GRN",
            sub_group="Auto Created",
            item_name="Acid",
            external_item_id="G1000003",
            unit="KG",
            opening_stock="0.000",
            current_stock="0.000",
        )
        grn = GRN.objects.create(
            grn_no="GRN-UNIT-001",
            trade_name="tester",
            gateentry_bookno="GE-UNIT-001",
            gateentry_bookdate=date(2026, 6, 18),
            raw_payload={
                "document_details": {MANUAL_GATE_ENTRY_FLAG: True},
                "supplier_details": {"trade_name": "tester"},
                "items": [
                    {"item_id": "G1000003", "product_description": "Acid", "quantity": "300.000", "unit": "Litre"},
                ],
            },
        )

        response = self.client.post(
            f"/api/grn/{grn.id}/move-to-qcr/",
            {"items": [{"received_qty": "250"}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        existing_item.refresh_from_db()
        self.assertEqual(existing_item.unit, "Litre")
        self.assertTrue(StoreTransaction.objects.filter(item=existing_item, reference_type=StoreTransaction.ReferenceType.GRN).exists())

    def test_warehouse_inventory_lists_qc_pending_rows_from_store_in_selection(self):
        grn = GRN.objects.create(
            grn_no="GRN-WH-001",
            po_no="PO-WH-001",
            trade_name="ABC Traders",
            item_id="ITEM-WH-001",
            product_description="Dell Server Rack",
            process_status=GRN.PROCESS_STATUS_GRN_PENDING,
            raw_payload={
                "document_details": {"po_no": "PO-WH-001"},
                "supplier_details": {"trade_name": "ABC Traders"},
                "items": [
                    {"item_id": "ITEM-WH-001", "product_description": "Dell Server Rack", "quantity": "10.000", "unit": "NOS"},
                    {"item_id": "ITEM-WH-002", "product_description": "LAN Cable", "quantity": "5.000", "unit": "NOS"},
                ],
            },
        )

        move_response = self.client.post(
            f"/api/grn/{grn.id}/move-pending-to-qcr/",
            {
                "items": [
                    {
                        "received_qty": "9",
                        "store_in_id": "101",
                        "store_in_name": "QC Pending Warehouse - CBE",
                    },
                    {
                        "received_qty": "5",
                        "store_in_id": "102",
                        "store_in_name": "Main Store",
                    },
                ]
            },
            format="json",
        )

        self.assertEqual(move_response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/warehouse-inventory/",
            {"warehouse_name": "QC Pending Warehouse - CBE"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertIsNone(response.data["previous"])

        row = response.data["results"][0]
        self.assertEqual(row["grn_no"], "GRN-WH-001")
        self.assertEqual(row["supplier"], "ABC Traders")
        self.assertEqual(row["po_no"], "PO-WH-001")
        self.assertEqual(row["items"], "Dell Server Rack")
        self.assertEqual(row["inward_qty"], "9")
        self.assertEqual(row["outward_qty"], "0")
        self.assertEqual(row["status"], GRN.PROCESS_STATUS_QCR)

    def test_warehouse_inventory_lists_rejected_rows_after_qcr_completion(self):
        _grn, qcr = self.create_active_qcr_record(grn_no="GRN-WH-REJ-001")

        update_response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {
                "action": "complete",
                "items": [
                    {"line_index": 0, "rejected_qty": "2", "reason": "Damaged during inspection"},
                    {"line_index": 1, "rejected_qty": "0", "reason": ""},
                ],
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            "/api/warehouse-inventory/",
            {"warehouse_name": "Rejected Warehouse - CBE"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        row = response.data["results"][0]
        self.assertEqual(row["grn_no"], "GRN-WH-REJ-001")
        self.assertEqual(row["supplier"], "Acme Polymers")
        self.assertEqual(row["items"], "QCR Line Item 1")
        self.assertEqual(row["inward_qty"], "2")
        self.assertEqual(row["reason"], "Damaged during inspection")

    def test_qcr_move_to_grn_reenables_record_in_grn_list(self):
        grn = GRN.objects.create(
            grn_no="GRN-102",
            grn_date=date(2026, 5, 5),
            trade_name="Acme Polymers",
            item_id="ITEM-GRN-102",
            product_description="Reenabled GRN Item",
            accepted_qty="8.00",
            unit="kg",
            raw_payload={
                "document_details": {
                    "grn_no": "GRN-102",
                    "grn_date": "2026-05-05",
                },
                "supplier_details": {
                    "trade_name": "Acme Polymers",
                },
                "items": [
                    {
                        "item_id": "ITEM-GRN-102",
                        "product_description": "Reenabled GRN Item",
                        "unit": "kg",
                        "accepted_qty": "8.000",
                    }
                ],
            },
            status=False,
            process_status="Moved to QCR",
        )
        qcr = QCR.objects.create(
            source_grn=grn,
            grn_reference_no=grn.grn_no,
            snapshot={"grn_no": grn.grn_no},
            status="Active",
            moved_to_qcr_at=grn.created_at,
        )

        update_response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {"action": "move_to_grn"},
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)

        grn.refresh_from_db()
        qcr.refresh_from_db()
        self.assertTrue(grn.status)
        self.assertEqual(grn.process_status, "GRN Approved")
        self.assertEqual(qcr.status, "Moved to GRN")

        list_response = self.client.get("/api/grn/")
        moved_grn_response = self.client.get("/api/grn/moved/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["data"], [])
        self.assertEqual(moved_grn_response.status_code, 200)
        self.assertEqual(len(moved_grn_response.json()["data"]), 1)
        self.assertEqual(moved_grn_response.json()["data"][0]["id"], grn.id)

        moved_response = self.client.get("/api/qcr/?tab=grn")

        self.assertEqual(moved_response.status_code, 200)
        self.assertEqual(len(moved_response.json()), 1)
        self.assertEqual(moved_response.json()[0]["id"], qcr.id)

    def test_qcr_move_to_grn_syncs_store_stock(self):
        payload = {
            "document_details": {
                "grn_no": "GRN-107",
                "grn_date": "2026-05-05",
            },
            "supplier_details": {
                "trade_name": "Acme Polymers",
            },
            "items": [
                {
                    "item_id": "ITEM-MOVE-001",
                    "product_description": "QCR Move Item",
                    "unit": "kg",
                    "accepted_qty": "12.500",
                }
            ],
        }
        grn = GRN.objects.create(
            grn_no="GRN-107",
            grn_date=date(2026, 5, 5),
            trade_name="Acme Polymers",
            item_id="ITEM-MOVE-001",
            product_description="QCR Move Item",
            accepted_qty="12.50",
            unit="kg",
            raw_payload=payload,
            status=False,
            process_status="Moved to QCR",
        )
        qcr = QCR.objects.create(
            source_grn=grn,
            grn_reference_no=grn.grn_no,
            snapshot={"grn_no": grn.grn_no},
            status="Active",
            moved_to_qcr_at=grn.created_at,
        )

        self.assertEqual(StoreStock.objects.count(), 0)
        self.assertEqual(StoreTransaction.objects.count(), 0)

        update_response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {"action": "move_to_grn"},
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)

        qcr.refresh_from_db()
        self.assertEqual(qcr.generated_grn_no, "GRN - WPE - 0001")

        item = Item.objects.get(external_item_id="ITEM-MOVE-001")
        stock_row = StoreStock.objects.get(item=item)
        store_transaction = StoreTransaction.objects.get(transaction_type=StoreTransaction.TransactionType.GRN_INWARD)

        self.assertEqual(item.item_name, "QCR Move Item")
        self.assertEqual(str(stock_row.quantity), "12.500")
        self.assertEqual(store_transaction.reference_id, "GRN - WPE - 0001:1")
        self.assertEqual(store_transaction.metadata["grn_no"], "GRN - WPE - 0001")
        self.assertEqual(store_transaction.metadata["generated_grn_no"], "GRN - WPE - 0001")
        self.assertEqual(store_transaction.metadata["grn_reference_no"], "GRN-107")
        self.assertEqual(
            StoreTransaction.objects.filter(
                transaction_type=StoreTransaction.TransactionType.GRN_INWARD,
            ).count(),
            1,
        )

    def test_qcr_complete_posts_accepted_and_rejected_stock_for_every_item(self):
        grn, qcr = self.create_active_qcr_record(grn_no="GRN-108")

        response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {
                "action": "complete",
                "items": [
                    {"line_index": 0, "rejected_qty": "2", "reason": "Damaged during inspection"},
                    {"line_index": 1, "rejected_qty": "0", "reason": ""},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["message"], "QCR completed with partial rejection.")

        grn.refresh_from_db()
        qcr.refresh_from_db()

        self.assertEqual(grn.process_status, GRN.PROCESS_STATUS_APPROVED)
        self.assertEqual(qcr.generated_grn_no, "GRN - WPE - 0001")
        self.assertEqual(grn.qc_status, "Partial")
        self.assertTrue(grn.status)
        self.assertEqual(str(grn.accepted_qty), "12.00")
        self.assertEqual(str(grn.rejected_qty), "2.00")
        self.assertEqual(qcr.status, GRN.PROCESS_STATUS_MOVED_TO_GRN)
        self.assertIsNotNone(qcr.qcr_completed_at)
        self.assertEqual(qcr.qcr_items[0]["accepted_qty"], "7")
        self.assertEqual(qcr.qcr_items[0]["rejected_qty"], "2")
        self.assertEqual(qcr.qcr_items[0]["rejection_reason"], "Damaged during inspection")
        self.assertEqual(qcr.qcr_items[1]["accepted_qty"], "5")
        self.assertEqual(grn.raw_payload["items"][0]["accepted_qty"], "7")
        self.assertEqual(grn.raw_payload["items"][0]["rejected_qty"], "2")
        self.assertEqual(grn.raw_payload["items"][0]["rejection_reason"], "Damaged during inspection")

        qc_pending = Warehouse.objects.get(code="QC_PENDING_CBE")
        store = Warehouse.objects.get(code="STORE")
        rejected = Warehouse.objects.get(code="REJECTED_CBE")
        first_item = Item.objects.get(external_item_id="GRN-108-ITEM-1")
        second_item = Item.objects.get(external_item_id="GRN-108-ITEM-2")

        self.assertEqual(str(StoreStock.objects.get(item=first_item, warehouse=qc_pending).quantity), "0.000")
        self.assertEqual(str(StoreStock.objects.get(item=second_item, warehouse=qc_pending).quantity), "0.000")
        self.assertEqual(str(StoreStock.objects.get(item=first_item, warehouse=store).quantity), "7.000")
        self.assertEqual(str(StoreStock.objects.get(item=second_item, warehouse=store).quantity), "5.000")
        self.assertEqual(str(StoreStock.objects.get(item=first_item, warehouse=rejected).quantity), "2.000")
        self.assertEqual(StoreStock.objects.filter(warehouse=store).count(), 2)
        self.assertEqual(StoreStock.objects.filter(warehouse=rejected).count(), 1)
        self.assertEqual(
            StoreTransaction.objects.filter(
                transaction_type=StoreTransaction.TransactionType.SR_ISSUE,
                reference_type=StoreTransaction.ReferenceType.GRN,
            ).count(),
            3,
        )
        self.assertEqual(
            StoreTransaction.objects.filter(
                transaction_type=StoreTransaction.TransactionType.SR_RECEIPT,
                reference_type=StoreTransaction.ReferenceType.GRN,
            ).count(),
            3,
        )
        self.assertTrue(
            GRNAuditLog.objects.filter(
                grn=grn,
                stage=GRNAuditLog.STAGE_ADDED_TO_STORE,
                notes__icontains="Main Store",
            ).exists()
        )
        self.assertTrue(
            GRNAuditLog.objects.filter(
                grn=grn,
                stage=GRNAuditLog.STAGE_QCR_REJECTED,
                notes__icontains="Rejected Warehouse - CBE",
            ).exists()
        )

    def test_qcr_complete_uses_product_name_when_external_item_id_points_to_different_item(self):
        qc_pending, _store, _rejected = self.ensure_qcr_workflow_warehouses()
        Item.objects.create(
            category="GRN Imported",
            group="Inbound GRN",
            sub_group="Auto Created",
            item_name="Test Product Description",
            external_item_id="ITEM001",
            unit="NOS",
            opening_stock="0.000",
            current_stock="0.000",
        )
        resolved_item = Item.objects.create(
            category="GRN Imported",
            group="Inbound GRN",
            sub_group="Auto Created",
            item_name="Dell Server Rack",
            unit="NOS",
            opening_stock="0.000",
            current_stock="0.000",
        )
        StoreStock.objects.create(item=resolved_item, warehouse=qc_pending, available_qty="10.000", reserved_qty="0.000")
        raw_payload = {
            "document_details": {
                "grn_no": "GRN-108-CONFLICT",
                "grn_date": "2026-05-05",
            },
            "supplier_details": {
                "trade_name": "Acme Polymers",
            },
            "items": [
                {
                    "item_id": "ITEM001",
                    "product_description": "Dell Server Rack",
                    "quantity": "10.000",
                    "received_qty": "10",
                    "accepted_qty": "10",
                    "rejected_qty": "0",
                    "unit": "NOS",
                    "store_in_id": str(qc_pending.id),
                    "store_in_name": qc_pending.name,
                }
            ],
        }
        pending_items = [
            {
                "line_index": 0,
                "item_id": "ITEM001",
                "item_name": "Dell Server Rack",
                "unit": "NOS",
                "sent_qty": "10.000",
                "received_qty": "10",
                "store_in_id": str(qc_pending.id),
                "store_in_name": qc_pending.name,
            }
        ]
        grn = GRN.objects.create(
            grn_no="GRN-108-CONFLICT",
            grn_date=date(2026, 5, 5),
            trade_name="Acme Polymers",
            item_id="ITEM001",
            product_description="Dell Server Rack",
            accepted_qty="10.00",
            rejected_qty="0.00",
            unit="NOS",
            raw_payload=raw_payload,
            grn_pending_items=pending_items,
            status=False,
            process_status=GRN.PROCESS_STATUS_QCR,
        )
        qcr = QCR.objects.create(
            source_grn=grn,
            grn_reference_no=grn.grn_no,
            snapshot={
                "grn_no": grn.grn_no,
                "raw_payload": raw_payload,
                "grn_pending_items": pending_items,
            },
            status="Active",
            moved_to_qcr_at=grn.created_at,
        )

        response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {
                "action": "complete",
                "items": [
                    {"line_index": 0, "rejected_qty": "2", "reason": "Damaged during inspection"},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        conflicting_item = Item.objects.get(external_item_id="ITEM001")
        resolved_item = Item.objects.get(item_name="Dell Server Rack")
        stock_row = StoreStock.objects.get(item=resolved_item, warehouse=Warehouse.objects.get(code="STORE"))

        self.assertEqual(conflicting_item.item_name, "Test Product Description")
        self.assertIsNone(resolved_item.external_item_id)
        self.assertEqual(str(stock_row.quantity), "8.000")
        self.assertFalse(StoreStock.objects.filter(item=conflicting_item, warehouse=Warehouse.objects.get(code="STORE")).exists())

    def test_qcr_complete_allows_blank_reason_when_rejected_qty_is_positive(self):
        _grn, qcr = self.create_active_qcr_record(grn_no="GRN-109")

        response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {
                "action": "complete",
                "items": [
                    {"line_index": 0, "rejected_qty": "1", "reason": ""},
                    {"line_index": 1, "rejected_qty": "0", "reason": ""},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_qcr_complete_rejects_quantity_above_received_qty(self):
        _grn, qcr = self.create_active_qcr_record(grn_no="GRN-110")

        response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {
                "action": "complete",
                "items": [
                    {"line_index": 0, "rejected_qty": "12", "reason": "Damaged during inspection"},
                    {"line_index": 1, "rejected_qty": "0", "reason": ""},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(
            response.data["errors"],
            {"items[0].rejected_qty": "Rejected Qty cannot exceed Received Qty."},
        )

    def test_qcr_list_shows_only_active_records_by_default(self):
        active_grn = GRN.objects.create(grn_no="GRN-103", status=False, process_status="Moved to QCR")
        active_qcr = QCR.objects.create(
            source_grn=active_grn,
            grn_reference_no=active_grn.grn_no,
            snapshot={"grn_no": active_grn.grn_no},
            status="Active",
            moved_to_qcr_at=active_grn.created_at,
        )

        moved_grn = GRN.objects.create(grn_no="GRN-104", status=True, process_status="Moved to GRN")
        QCR.objects.create(
            source_grn=moved_grn,
            grn_reference_no=moved_grn.grn_no,
            snapshot={"grn_no": moved_grn.grn_no},
            status="Moved to GRN",
            moved_to_qcr_at=moved_grn.created_at,
        )

        rejected_grn = GRN.objects.create(grn_no="GRN-105", status=False, process_status="Rejected")
        QCR.objects.create(
            source_grn=rejected_grn,
            grn_reference_no=rejected_grn.grn_no,
            snapshot={"grn_no": rejected_grn.grn_no},
            status="Rejected",
            moved_to_qcr_at=rejected_grn.created_at,
        )

        response = self.client.get("/api/qcr/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], active_qcr.id)

    def test_completed_qcr_endpoint_returns_one_record_with_all_item_lines(self):
        _grn, qcr = self.create_active_qcr_record(grn_no="GRN-111")

        update_response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {
                "action": "complete",
                "items": [
                    {"line_index": 0, "rejected_qty": "2", "reason": "Damaged during inspection"},
                    {"line_index": 1, "rejected_qty": "0", "reason": ""},
                ],
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        completed_response = self.client.get("/api/qcr/completed/")

        self.assertEqual(completed_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(completed_response.json()), 1)
        row = completed_response.json()[0]
        self.assertEqual(row["generated_grn_no"], "GRN - WPE - 0001")
        self.assertEqual(len(row["items"]), 2)
        self.assertEqual(row["items"][0]["item_name"], "QCR Line Item 1")
        self.assertEqual(row["items"][0]["accepted_qty"], "7")
        self.assertEqual(row["items"][0]["rejected_qty"], "2")
        self.assertEqual(row["items"][1]["item_name"], "QCR Line Item 2")
        self.assertEqual(row["items"][1]["accepted_qty"], "5")
        self.assertEqual(row["source_grn_data"]["items"][1]["product_description"], "QCR Line Item 2")

    def test_rejected_qcr_records_are_listed_in_cancelled_tab_view(self):
        grn = GRN.objects.create(grn_no="GRN-106", status=False, process_status="Moved to QCR")
        qcr = QCR.objects.create(
            source_grn=grn,
            grn_reference_no=grn.grn_no,
            snapshot={"grn_no": grn.grn_no},
            status="Active",
            moved_to_qcr_at=grn.created_at,
        )

        update_response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {"action": "reject", "remarks": "Rejected during test"},
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)

        qcr_tab_response = self.client.get("/api/qcr/")
        cancelled_response = self.client.get("/api/qcr/?tab=cancelled")
        cancelled_route_response = self.client.get("/api/qcr/cancelled/")
        rejected_alias_response = self.client.get("/api/qcr/?status=rejected")

        self.assertEqual(qcr_tab_response.status_code, 200)
        self.assertEqual(qcr_tab_response.json(), [])
        self.assertEqual(cancelled_response.status_code, 200)
        self.assertEqual(len(cancelled_response.json()), 1)
        self.assertEqual(cancelled_response.json()[0]["id"], qcr.id)
        self.assertEqual(cancelled_route_response.status_code, 200)
        self.assertEqual(len(cancelled_route_response.json()), 1)
        self.assertEqual(cancelled_route_response.json()[0]["id"], qcr.id)
        self.assertEqual(rejected_alias_response.status_code, 200)
        self.assertEqual(len(rejected_alias_response.json()), 1)
        self.assertEqual(rejected_alias_response.json()[0]["id"], qcr.id)

    def test_partially_rejected_qcr_records_are_listed_in_both_completed_and_rejected_views(self):
        _grn, qcr = self.create_active_qcr_record(grn_no="GRN-111")

        update_response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {
                "action": "complete",
                "items": [
                    {"line_index": 0, "rejected_qty": "2", "reason": "Damaged during inspection"},
                    {"line_index": 1, "rejected_qty": "0", "reason": ""},
                ],
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        completed_response = self.client.get("/api/qcr/?tab=grn")
        rejected_response = self.client.get("/api/qcr/?tab=cancelled")

        self.assertEqual(completed_response.status_code, 200)
        self.assertEqual(rejected_response.status_code, 200)
        self.assertEqual([row["id"] for row in completed_response.json()], [qcr.id])
        self.assertEqual([row["id"] for row in rejected_response.json()], [qcr.id])
