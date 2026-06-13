from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.items.models import Item
from apps.store.models import StoreTransaction
from apps.store.services import apply_inward_stock, apply_outward_stock, get_warehouse_by_name


UserModel = get_user_model()


class WarehouseInventorySummaryApiTests(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(
            username="warehouse-inventory-user",
            email="warehouse-inventory@example.com",
            password="password123",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        self.url = "/api/inventory/warehouse-inventory/"

    def test_requires_warehouse_name_and_returns_summary_for_selected_warehouse(self):
        warehouse = get_warehouse_by_name("QC Pending Warehouse - CBE")
        primary_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="hdpe",
            item_name="Warehouse Summary Primary",
            unit="kg",
        )
        secondary_item = Item.objects.create(
            category="Consumable",
            group="packing",
            sub_group="labels",
            item_name="Warehouse Summary Secondary",
            unit="pcs",
        )
        apply_inward_stock(
            item=primary_item,
            warehouse=warehouse,
            quantity="12.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="WH-QC-OPEN-1",
            created_by=self.user,
            transaction_date="2026-06-01",
        )
        apply_outward_stock(
            item=primary_item,
            warehouse=warehouse,
            quantity="2.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_OUTWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="WH-QC-OUT-1",
            created_by=self.user,
            transaction_date="2026-06-02",
        )
        apply_inward_stock(
            item=secondary_item,
            warehouse=warehouse,
            quantity="5.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="WH-QC-IN-2",
            created_by=self.user,
            transaction_date="2026-06-03",
        )

        response = self.client.get(
            self.url,
            {
                "warehouse_name": "QC Pending Warehouse - CBE",
                "item_id": primary_item.id,
                "search": "Primary",
                "page": 1,
                "page_size": 10,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 1)
        row = response.data["data"]["results"][0]
        self.assertEqual(row["item_id"], primary_item.id)
        self.assertEqual(row["item_name"], primary_item.item_name)
        self.assertEqual(row["current_stock"], "10.000")
        self.assertEqual(row["total_inward"], "12.000")
        self.assertEqual(row["total_outward"], "2.000")
        self.assertTrue(row["last_updated"])

    def test_missing_warehouse_name_is_rejected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("warehouse_name", response.data)
