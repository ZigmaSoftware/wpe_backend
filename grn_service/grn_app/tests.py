import re

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import GRN, QCR


class GRNAPIViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("grn-create")
        self.receiver_url = reverse("grn-receiver-create")
        self.view_url = reverse("grn-view-list")
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
        response = self.client.post(self.receiver_url, self.build_receiver_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data,
            {"status": "sent", "message": "GRN received successfully"},
        )

        grn = GRN.objects.get(grn_no="GRN-RCV-001")
        self.assertEqual(grn.po_no, "PO-RCV-001")
        self.assertEqual(grn.supplier_id, "SUP-RCV-001")
        self.assertEqual(grn.item_id, "ITEM-RCV-001")
        self.assertEqual(grn.raw_payload["items"][1]["item_id"], "ITEM-RCV-002")
        self.assertTrue(re.fullmatch(r"WPE-\d{8}", grn.unique_id))

    def test_grn_receiver_duplicate_returns_200_without_creating_duplicate(self):
        payload = self.build_receiver_payload("GRN-RCV-DUP")

        first_response = self.client.post(self.receiver_url, payload, format="json")
        duplicate_response = self.client.post(self.receiver_url, payload, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            duplicate_response.data,
            {"status": "duplicate", "message": "GRN already exists"},
        )
        self.assertEqual(GRN.objects.filter(grn_no="GRN-RCV-DUP").count(), 1)

    def test_grn_receiver_invalid_payload_returns_400(self):
        payload = self.build_receiver_payload("GRN-RCV-BAD")
        payload["document_details"]["po_no"] = ""
        payload["items"] = []

        response = self.client.post(self.receiver_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["message"], "Validation failed")
        self.assertIn("document_details.po_no", response.data["errors"])
        self.assertIn("items", response.data["errors"])
        self.assertFalse(GRN.objects.filter(grn_no="GRN-RCV-BAD").exists())

    def test_get_grn_list_returns_not_found_for_missing_grn(self):
        response = self.client.get(self.url, {"grn_no": "GRN-404"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["count"], 0)


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
