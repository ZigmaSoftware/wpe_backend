from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import GRN, QCR


class GRNAPIViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("grn-create")
        self.view_url = reverse("grn-view-list")
        self.api_root_url = "/api/grn"
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

    def test_grn_api_root_returns_browsable_link(self):
        response = self.client.get(self.api_root_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("view", response.data)
        self.assertTrue(response.data["view"].endswith("/api/grnview/"))

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
