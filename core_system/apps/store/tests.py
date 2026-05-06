from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.blending.models import BlendingStock
from apps.items.models import Item, ItemStockTransaction

from .models import StockRequest, StoreStock, StoreTransaction
from .services import add_stock_from_grn


@override_settings(INTERNAL_API_KEY="test-internal-key")
class StoreWorkflowTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="store-user",
            password="test-pass-123",
        )
        access_token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    def test_approve_request_transfers_store_stock_to_blending(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="ldpe",
            item_name="Virgin LDPE",
            unit="kg",
            opening_stock=Decimal("100.000"),
            current_stock=Decimal("100.000"),
        )
        StoreStock.objects.create(item=item, quantity=Decimal("100.000"))

        request_response = self.client.post(
            "/api/store/request-stock/",
            {
                "item_id": item.id,
                "quantity": "50.000",
            },
            format="json",
        )

        self.assertEqual(request_response.status_code, 201)
        request_id = request_response.data["request"]["id"]

        approve_response = self.client.post(f"/api/store/approve-request/{request_id}/", {}, format="json")

        self.assertEqual(approve_response.status_code, 200)

        item.refresh_from_db()
        store_stock = StoreStock.objects.get(item=item)
        blending_stock = BlendingStock.objects.get(item=item)
        stock_request = StockRequest.objects.get(pk=request_id)

        self.assertEqual(item.current_stock, Decimal("50.000"))
        self.assertEqual(store_stock.quantity, Decimal("50.000"))
        self.assertEqual(blending_stock.quantity, Decimal("50.000"))
        self.assertEqual(stock_request.status, StockRequest.Status.APPROVED)
        self.assertEqual(stock_request.approved_by, self.user)

        self.assertEqual(
            StoreTransaction.objects.filter(
                item=item,
                transaction_type=StoreTransaction.TransactionType.TRANSFER_OUT,
            ).count(),
            1,
        )
        self.assertEqual(
            ItemStockTransaction.objects.filter(item=item, ref_id=f"REQ-{request_id}").count(),
            2,
        )

    def test_reject_request_leaves_stock_unchanged(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="blend",
            item_name="Blend Additive",
            unit="kg",
            opening_stock=Decimal("10.000"),
            current_stock=Decimal("10.000"),
        )
        StoreStock.objects.create(item=item, quantity=Decimal("10.000"))

        request_response = self.client.post(
            "/api/store/request-stock/",
            {
                "item_id": item.id,
                "quantity": "5.000",
            },
            format="json",
        )

        self.assertEqual(request_response.status_code, 201)
        request_id = request_response.data["request"]["id"]

        reject_response = self.client.post(f"/api/store/reject-request/{request_id}/", {}, format="json")

        self.assertEqual(reject_response.status_code, 200)

        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("10.000"))
        self.assertEqual(StoreStock.objects.get(item=item).quantity, Decimal("10.000"))
        self.assertFalse(BlendingStock.objects.filter(item=item).exists())
        self.assertEqual(StockRequest.objects.get(pk=request_id).status, StockRequest.Status.REJECTED)
        self.assertFalse(
            StoreTransaction.objects.filter(
                item=item,
                transaction_type=StoreTransaction.TransactionType.TRANSFER_OUT,
            ).exists()
        )

    def test_add_stock_from_grn_is_idempotent(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="eva",
            item_name="EVA Resin",
            unit="kg",
            opening_stock=Decimal("0.000"),
            current_stock=Decimal("0.000"),
        )

        payload = {
            "unique_id": "WPE-00000001",
            "document_details": {
                "grn_no": "GRN-1001",
                "grn_date": "2026-05-05",
            },
            "supplier_details": {
                "trade_name": "Acme Polymers",
            },
            "items": [
                {
                    "item_id": str(item.id),
                    "product_description": item.item_name,
                    "unit": "kg",
                    "accepted_qty": "12.500",
                }
            ],
        }

        first_result = add_stock_from_grn(payload)
        second_result = add_stock_from_grn(payload)

        item.refresh_from_db()
        store_stock = StoreStock.objects.get(item=item)

        self.assertEqual(first_result["processed_references"], ["WPE-00000001:1"])
        self.assertEqual(second_result["processed_references"], [])
        self.assertEqual(second_result["skipped_references"], ["WPE-00000001:1"])
        self.assertEqual(item.current_stock, Decimal("12.500"))
        self.assertEqual(store_stock.quantity, Decimal("12.500"))
        self.assertEqual(
            StoreTransaction.objects.filter(
                item=item,
                transaction_type=StoreTransaction.TransactionType.GRN_IN,
            ).count(),
            1,
        )
        self.assertEqual(ItemStockTransaction.objects.filter(item=item, ref_id="WPE-00000001:1").count(), 1)
