from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.admin_master.models import Staff, UserCreation, UserType
from apps.items.models import Item

from .models import StockRequest, StoreStock, StoreTransaction
from .services import add_stock_from_grn, apply_inward_stock, get_blending_warehouse, get_store_warehouse


@override_settings(INTERNAL_API_KEY="test-internal-key")
class StoreWorkflowTests(APITestCase):
    def create_role_user(self, *, username: str, role_name: str):
        user = get_user_model().objects.create_user(username=username, password="test-pass-123")
        staff = Staff.objects.create(name=f"{username} Staff")
        user_type = UserType.objects.create(name=role_name)
        UserCreation.objects.create(user=user, staff=staff, user_type=user_type)
        return user

    def make_auth_client(self, user):
        access_token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        return client

    def setUp(self):
        self.store_user = self.create_role_user(username="store-user", role_name="Store User")
        self.blending_user = self.create_role_user(username="blending-user", role_name="Blending User")
        self.store_client = self.make_auth_client(self.store_user)
        self.blending_client = self.make_auth_client(self.blending_user)
        self.store_warehouse = get_store_warehouse()
        self.blending_warehouse = get_blending_warehouse()

    def test_approve_request_transfers_stock_between_store_and_blending_warehouses(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="ldpe",
            item_name="Virgin LDPE",
            unit="kg",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.store_warehouse,
            quantity="100.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="OPEN-1",
            created_by=self.store_user,
        )

        request_response = self.blending_client.post(
            "/api/blending/store-requests/",
            {
                "remarks": "Material needed for batch 24-A",
                "items": [
                    {
                        "item_id": item.id,
                        "quantity": "50.000",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(request_response.status_code, 201)
        self.assertTrue(request_response.data["success"])
        request_id = request_response.data["data"]["id"]

        queue_response = self.store_client.get("/api/store/requests/?status=PENDING")
        self.assertEqual(queue_response.status_code, 200)
        self.assertEqual(queue_response.data["data"]["count"], 1)
        queued_item = queue_response.data["data"]["results"][0]["items"][0]
        self.assertEqual(queued_item["available_qty"], "100.000")
        self.assertEqual(queued_item["shortage_qty"], "0.000")

        approve_response = self.store_client.post(
            f"/api/store/requests/{request_id}/approve/",
            {"approval_remarks": "Approved for production batch 24-A"},
            format="json",
        )

        self.assertEqual(approve_response.status_code, 200)
        self.assertTrue(approve_response.data["success"])

        stock_request = StockRequest.objects.prefetch_related("items").get(pk=request_id)
        source_stock = StoreStock.objects.get(item=item, warehouse=self.store_warehouse)
        destination_stock = StoreStock.objects.get(item=item, warehouse=self.blending_warehouse)
        request_item = stock_request.items.get(item=item)

        self.assertEqual(stock_request.status, StockRequest.Status.APPROVED)
        self.assertEqual(stock_request.action_by, self.store_user)
        self.assertEqual(source_stock.available_qty, Decimal("50.000"))
        self.assertEqual(destination_stock.available_qty, Decimal("50.000"))
        self.assertEqual(request_item.approved_qty, Decimal("50.000"))
        self.assertEqual(request_item.issued_qty, Decimal("50.000"))
        self.assertEqual(
            StoreTransaction.objects.filter(
                item=item,
                transaction_type=StoreTransaction.TransactionType.SR_ISSUE,
            ).count(),
            1,
        )
        self.assertEqual(
            StoreTransaction.objects.filter(
                item=item,
                transaction_type=StoreTransaction.TransactionType.SR_RECEIPT,
            ).count(),
            1,
        )

    def test_reject_request_keeps_stock_unchanged(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="blend",
            item_name="Blend Additive",
            unit="kg",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.store_warehouse,
            quantity="10.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="OPEN-2",
            created_by=self.store_user,
        )

        request_response = self.blending_client.post(
            "/api/blending/store-requests/",
            {
                "items": [{"item_id": item.id, "quantity": "5.000"}],
            },
            format="json",
        )
        request_id = request_response.data["data"]["id"]

        reject_response = self.store_client.post(
            f"/api/store/requests/{request_id}/reject/",
            {"approval_remarks": "Rejected due to plan change"},
            format="json",
        )

        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(
            StoreStock.objects.get(item=item, warehouse=self.store_warehouse).available_qty,
            Decimal("10.000"),
        )
        self.assertFalse(StoreStock.objects.filter(item=item, warehouse=self.blending_warehouse).exists())
        self.assertEqual(StockRequest.objects.get(pk=request_id).status, StockRequest.Status.REJECTED)
        self.assertFalse(
            StoreTransaction.objects.filter(
                item=item,
                transaction_type=StoreTransaction.TransactionType.SR_ISSUE,
            ).exists()
        )

    def test_add_stock_from_grn_is_idempotent(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="eva",
            item_name="EVA Resin",
            unit="kg",
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

        first_result = add_stock_from_grn(payload, created_by=self.store_user)
        second_result = add_stock_from_grn(payload, created_by=self.store_user)

        stock_row = StoreStock.objects.get(item=item, warehouse=self.store_warehouse)

        self.assertEqual(first_result["processed_references"], ["WPE-00000001:1"])
        self.assertEqual(second_result["processed_references"], [])
        self.assertEqual(second_result["skipped_references"], ["WPE-00000001:1"])
        self.assertEqual(stock_row.available_qty, Decimal("12.500"))
        self.assertEqual(
            StoreTransaction.objects.filter(
                item=item,
                warehouse=self.store_warehouse,
                transaction_type=StoreTransaction.TransactionType.GRN_INWARD,
            ).count(),
            1,
        )

    def test_outward_api_prevents_negative_inventory(self):
        item = Item.objects.create(
            category="General Item",
            group="consumable",
            sub_group="packing",
            item_name="Tape Roll",
            unit="pcs",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.store_warehouse,
            quantity="5.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="OPEN-3",
            created_by=self.store_user,
        )

        outward_response = self.store_client.post(
            "/api/store/stock/outward/",
            {
                "item_id": item.id,
                "warehouse_id": self.store_warehouse.id,
                "quantity": "6.000",
                "transaction_type": StoreTransaction.TransactionType.MANUAL_OUTWARD,
                "reference_type": StoreTransaction.ReferenceType.MANUAL,
                "reference_id": "MAN-OUT-1",
            },
            format="json",
        )

        self.assertEqual(outward_response.status_code, 400)
        self.assertEqual(
            StoreStock.objects.get(item=item, warehouse=self.store_warehouse).available_qty,
            Decimal("5.000"),
        )

    def test_blending_user_cannot_approve_requests(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="lldpe",
            item_name="LLDPE Resin",
            unit="kg",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.store_warehouse,
            quantity="10.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="OPEN-4",
            created_by=self.store_user,
        )
        request_response = self.blending_client.post(
            "/api/blending/store-requests/",
            {"items": [{"item_id": item.id, "quantity": "2.000"}]},
            format="json",
        )
        request_id = request_response.data["data"]["id"]

        approve_response = self.blending_client.post(
            f"/api/store/requests/{request_id}/approve/",
            {"approval_remarks": "Should not be allowed"},
            format="json",
        )

        self.assertEqual(approve_response.status_code, 403)
