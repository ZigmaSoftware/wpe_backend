from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import GRN


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
