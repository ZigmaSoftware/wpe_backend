from decimal import Decimal

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.items.models import Item, ItemStockTransaction

from .models import DepartmentStock, StockTransfer


@override_settings(INTERNAL_API_KEY="test-internal-key")
class BlendingStockTransferTests(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_KEY="test-internal-key")

    def test_request_stock_transfers_store_stock_to_blending(self):
        create_response = self.client.post(
            "/api/items",
            {
                "category": "Raw Material",
                "group": "polymer",
                "sub_group": "ldpe",
                "item_name": "Virgin LDPE",
                "unit": "kg",
                "opening_stock": "100.000",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        item = Item.objects.get()

        transfer_response = self.client.post(
            "/api/blending/request-stock/",
            {
                "item_id": item.id,
                "quantity": "50.000",
            },
            format="json",
        )

        self.assertEqual(transfer_response.status_code, 201)

        item.refresh_from_db()
        store_stock = DepartmentStock.objects.get(item=item, department=DepartmentStock.Department.STORE)
        blending_stock = DepartmentStock.objects.get(item=item, department=DepartmentStock.Department.BLENDING)
        transfer = StockTransfer.objects.get(item=item)

        self.assertEqual(item.current_stock, Decimal("50.000"))
        self.assertEqual(store_stock.quantity, Decimal("50.000"))
        self.assertEqual(blending_stock.quantity, Decimal("50.000"))
        self.assertEqual(transfer.status, StockTransfer.Status.COMPLETED)
        self.assertIsNotNone(transfer.completed_at)

        transfer_transactions = ItemStockTransaction.objects.filter(
            item=item,
            trans_type__in=["TRANSFER OUT (BLENDING)", "TRANSFER IN (STORE)"],
        ).order_by("id")

        self.assertEqual(transfer_transactions.count(), 2)
        self.assertEqual(transfer_transactions[0].outwards, Decimal("50.000"))
        self.assertEqual(transfer_transactions[0].warehouse, DepartmentStock.Department.STORE)
        self.assertEqual(transfer_transactions[1].inwards, Decimal("50.000"))
        self.assertEqual(transfer_transactions[1].warehouse, DepartmentStock.Department.BLENDING)

    def test_blending_stock_list_returns_items_with_positive_blending_balance(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="mix",
            item_name="Mixer Resin",
            unit="kg",
            opening_stock=Decimal("0.000"),
            current_stock=Decimal("25.000"),
        )
        DepartmentStock.objects.create(
            item=item,
            department=DepartmentStock.Department.STORE,
            quantity=Decimal("25.000"),
        )
        DepartmentStock.objects.create(
            item=item,
            department=DepartmentStock.Department.BLENDING,
            quantity=Decimal("10.000"),
        )

        response = self.client.get("/api/blending/stock/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["item"], item.id)
        self.assertEqual(response.data[0]["department"], DepartmentStock.Department.BLENDING)
        self.assertEqual(response.data[0]["quantity"], "10.000")

    def test_request_stock_rejects_when_store_balance_is_insufficient(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="blend",
            item_name="Blend Additive",
            unit="kg",
            opening_stock=Decimal("10.000"),
            current_stock=Decimal("10.000"),
        )
        DepartmentStock.objects.create(
            item=item,
            department=DepartmentStock.Department.STORE,
            quantity=Decimal("10.000"),
        )

        response = self.client.post(
            "/api/blending/request-stock/",
            {
                "item_id": item.id,
                "quantity": "12.000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("10.000"))
        self.assertEqual(
            DepartmentStock.objects.get(item=item, department=DepartmentStock.Department.STORE).quantity,
            Decimal("10.000"),
        )
        self.assertFalse(
            DepartmentStock.objects.filter(item=item, department=DepartmentStock.Department.BLENDING).exists()
        )
        self.assertFalse(StockTransfer.objects.filter(item=item).exists())

    def test_existing_inward_and_outward_keep_store_department_in_sync(self):
        create_response = self.client.post(
            "/api/items",
            {
                "category": "Raw Material",
                "group": "polymer",
                "sub_group": "eva",
                "item_name": "EVA Resin",
                "unit": "kg",
                "opening_stock": "20.000",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        item = Item.objects.get(item_name="EVA Resin")

        inward_response = self.client.post(
            f"/api/items/{item.id}/stock/inward/",
            {"quantity": "5.000"},
            format="json",
        )
        outward_response = self.client.post(
            f"/api/items/{item.id}/stock/outward/",
            {"quantity": "3.000"},
            format="json",
        )

        self.assertEqual(inward_response.status_code, 201)
        self.assertEqual(outward_response.status_code, 201)

        item.refresh_from_db()
        store_stock = DepartmentStock.objects.get(item=item, department=DepartmentStock.Department.STORE)

        self.assertEqual(item.current_stock, Decimal("22.000"))
        self.assertEqual(store_stock.quantity, Decimal("22.000"))
