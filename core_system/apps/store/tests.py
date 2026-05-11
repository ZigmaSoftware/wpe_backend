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

    def test_approve_request_transfers_stock_between_warehouses(self):
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
                "items": [{"item_id": item.id, "quantity": "50.000"}],
            },
            format="json",
        )
        request_id = request_response.data["data"]["id"]

        approve_response = self.store_client.post(
            f"/api/store/requests/{request_id}/approve/",
            {"approval_remarks": "Approved for production"},
            format="json",
        )

        self.assertEqual(approve_response.status_code, 200)
        source_stock = StoreStock.objects.get(item=item, warehouse=self.store_warehouse)
        destination_stock = StoreStock.objects.get(item=item, warehouse=self.blending_warehouse)
        request_item = StockRequest.objects.prefetch_related("items").get(pk=request_id).items.get(item=item)

        self.assertEqual(source_stock.available_qty, Decimal("50.000"))
        self.assertEqual(destination_stock.available_qty, Decimal("50.000"))
        self.assertEqual(request_item.approved_qty, Decimal("50.000"))
        self.assertEqual(request_item.issued_qty, Decimal("50.000"))

    def test_legacy_request_stock_endpoint_sets_additive_metadata(self):
        item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Processing Additive A",
            unit="kg",
        )

        response = self.blending_client.post(
            "/api/store/request-stock/",
            {
                "item_id": item.id,
                "quantity": "5.000",
                "request_type": "ADDITIVE",
                "department": "BLENDING",
                "requested_for_name": "Shift Lead",
                "request_reason": "Batch replenishment",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        stock_request = StockRequest.objects.prefetch_related("items").get(pk=response.data["request"]["id"])
        self.assertEqual(stock_request.request_type, StockRequest.RequestType.ADDITIVE)
        self.assertEqual(stock_request.department, "BLENDING")
        self.assertEqual(stock_request.requested_for_name, "Shift Lead")
        self.assertEqual(stock_request.request_reason, "Batch replenishment")
        self.assertEqual(stock_request.items.first().requested_qty, Decimal("5.000"))

    def test_store_requests_list_exposes_flat_compatibility_fields(self):
        item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Mixer Additive",
            unit="kg",
        )
        self.blending_client.post(
            "/api/store/request-stock/",
            {
                "item_id": item.id,
                "quantity": "2.500",
                "request_type": "ADDITIVE",
                "department": "BLENDING",
                "requested_for_name": "Mixer Operator",
                "request_reason": "Line refill",
            },
            format="json",
        )

        response = self.store_client.get("/api/store/requests/")

        self.assertEqual(response.status_code, 200)
        row = response.data["data"]["results"][0]
        self.assertEqual(row["item"], item.id)
        self.assertEqual(row["quantity"], "2.500")
        self.assertEqual(row["request_type"], "ADDITIVE")
        self.assertEqual(row["requested_for_name"], "Mixer Operator")

    def test_store_stock_list_is_readable_by_blending_user(self):
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
            reference_id="OPEN-2",
            created_by=self.store_user,
        )

        response = self.blending_client.get("/api/store/stock/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["results"][0]["quantity"], "5.000")

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
