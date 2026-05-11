import re
from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.items.models import Item
from apps.store.models import StoreStock, StoreTransaction
from .models import GRN, QCR


class GRNAPIViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("grn-create")
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

        first_item = Item.objects.get(external_item_id="ITEM-RCV-001")
        second_item = Item.objects.get(external_item_id="ITEM-RCV-002")
        self.assertEqual(first_item.item_name, "Receiver Item 1")
        self.assertEqual(second_item.item_name, "Receiver Item 2")
        self.assertEqual(str(first_item.current_stock), "10.000")
        self.assertEqual(str(second_item.current_stock), "5.000")
        self.assertEqual(str(StoreStock.objects.get(item=first_item).quantity), "10.000")
        self.assertEqual(str(StoreStock.objects.get(item=second_item).quantity), "5.000")
        self.assertEqual(
            StoreTransaction.objects.filter(
                transaction_type=StoreTransaction.TransactionType.GRN_IN,
            ).count(),
            2,
        )

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
        self.assertEqual(Item.objects.filter(external_item_id__in=["ITEM-RCV-001", "ITEM-RCV-002"]).count(), 2)
        self.assertEqual(
            StoreTransaction.objects.filter(
                transaction_type=StoreTransaction.TransactionType.GRN_IN,
            ).count(),
            2,
        )

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

    def test_grn_receiver_reuses_existing_item_by_product_name_and_backfills_external_item_id(self):
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
        self.assertEqual(existing_item.external_item_id, "ITEM-RCV-001")
        self.assertEqual(str(existing_item.current_stock), "10.000")
        self.assertEqual(Item.objects.filter(item_name="Receiver Item 1").count(), 1)
        self.assertEqual(Item.objects.filter(external_item_id="ITEM-RCV-002").count(), 1)

    def test_grn_receiver_returns_400_when_item_id_and_product_name_map_to_different_store_items(self):
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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["message"], "Payload validation failed.")
        self.assertEqual(response.data["response_code"], "WPE-VAL-000400")
        self.assertEqual(response.data["grn_no"], "GRN-RCV-CONFLICT")
        self.assertEqual(
            response.data["errors"],
            {
                "item_id": ["Sender item ID matches a different store item than the product name provided."],
                "product_description": [
                    "Product name matches a different store item than the sender item ID provided."
                ],
            },
        )
        self.assertFalse(GRN.objects.filter(grn_no="GRN-RCV-CONFLICT").exists())
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


class GRNQCRFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_moved_grn_is_removed_from_grn_list(self):
        grn = GRN.objects.create(grn_no="GRN-101")

        move_response = self.client.post(f"/api/grn/{grn.id}/move-to-qcr/", {}, format="json")

        self.assertEqual(move_response.status_code, 201)

        grn.refresh_from_db()
        self.assertFalse(grn.status)
        self.assertEqual(grn.process_status, "Moved to QCR")

        list_response = self.client.get("/api/grn/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["data"], [])

    def test_qcr_move_to_grn_reenables_record_in_grn_list(self):
        grn = GRN.objects.create(grn_no="GRN-102", status=False, process_status="Moved to QCR")
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
        self.assertEqual(grn.process_status, "Moved to GRN")
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
            {"action": "reject"},
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
