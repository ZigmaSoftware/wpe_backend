from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.admin_master.models import Staff, UserCreation, UserType
from apps.items.models import Item
from apps.store.models import StockRequest, StoreTransaction
from apps.store.services import apply_inward_stock, get_blending_warehouse, get_store_warehouse


@override_settings(INTERNAL_API_KEY="test-internal-key")
class BlendingStoreRequestTests(APITestCase):
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
        self.blending_user = self.create_role_user(username="blending-user", role_name="Blending User")
        self.store_user = self.create_role_user(username="store-user", role_name="Store User")
        self.client = self.make_auth_client(self.blending_user)
        self.store_user_client = self.make_auth_client(self.store_user)
        self.blending_warehouse = get_blending_warehouse()
        self.store_warehouse = get_store_warehouse()

    def test_request_stock_creates_pending_store_request_with_items(self):
        item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Processing Additive A",
            unit="kg",
        )

        response = self.client.post(
            "/api/blending/store-requests/",
            {
                "remarks": "Need material for mixing line 1",
                "request_type": "ADDITIVE",
                "department": "BLENDING",
                "requested_for_name": "Blending Supervisor",
                "request_reason": "Required for additive batch run",
                "items": [{"item_id": item.id, "quantity": "50.000"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["status"], StockRequest.Status.PENDING)
        self.assertEqual(response.data["data"]["request_type"], StockRequest.RequestType.ADDITIVE)
        self.assertEqual(response.data["data"]["item"], item.id)

    def test_legacy_additive_request_endpoint_still_works(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="lldpe",
            item_name="Legacy Requestable Resin",
            unit="kg",
        )

        response = self.client.post(
            "/api/blending/request-stock/",
            {
                "item_id": item.id,
                "quantity": "10.000",
                "requested_for_name": "Shift Lead",
                "request_reason": "Line refill",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["request"]["request_type"], "ADDITIVE")

    def test_request_stock_get_returns_requestable_store_stock_for_dropdown(self):
        additive_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Dropdown Additive",
            unit="kg",
        )
        non_additive_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="lldpe",
            item_name="Dropdown Resin",
            unit="kg",
        )
        apply_inward_stock(
            item=additive_item,
            warehouse=self.store_warehouse,
            quantity="12.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-DD-1",
            created_by=self.store_user,
        )
        apply_inward_stock(
            item=non_additive_item,
            warehouse=self.store_warehouse,
            quantity="7.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-DD-2",
            created_by=self.store_user,
        )

        response = self.client.get("/api/blending/request-stock/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 2)
        self.assertEqual(
            {row["item"] for row in response.data["data"]["results"]},
            {additive_item.id, non_additive_item.id},
        )
        self.assertEqual(
            {row["warehouse_code"] for row in response.data["data"]["results"]},
            {self.store_warehouse.code},
        )

    def test_request_stock_get_supports_search_against_store_dropdown_data(self):
        matching_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Searchable Additive Alpha",
            unit="kg",
        )
        non_matching_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Other Additive Beta",
            unit="kg",
        )
        apply_inward_stock(
            item=matching_item,
            warehouse=self.store_warehouse,
            quantity="12.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-SRCH-1",
            created_by=self.store_user,
        )
        apply_inward_stock(
            item=non_matching_item,
            warehouse=self.store_warehouse,
            quantity="9.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-SRCH-2",
            created_by=self.store_user,
        )

        response = self.client.get("/api/blending/request-stock/?search=Alpha")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(response.data["data"]["results"][0]["item"], matching_item.id)

    def test_cancel_pending_request(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="eva",
            item_name="EVA Resin",
            unit="kg",
        )
        create_response = self.client.post(
            "/api/blending/store-requests/",
            {"items": [{"item_id": item.id, "quantity": "5.000"}]},
            format="json",
        )
        request_id = create_response.data["data"]["id"]

        cancel_response = self.client.post(
            f"/api/blending/store-requests/{request_id}/cancel/",
            {"remarks": "Requirement changed"},
            format="json",
        )

        self.assertEqual(cancel_response.status_code, 200)
        self.assertEqual(cancel_response.data["data"]["status"], StockRequest.Status.CANCELLED)

    def test_pending_store_request_can_be_updated_and_returns_all_item_details(self):
        item_one = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Base Additive",
            unit="kg",
        )
        item_two = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Second Additive",
            unit="kg",
        )

        create_response = self.client.post(
            "/api/blending/store-requests/",
            {
                "request_type": "ADDITIVE",
                "requested_for_name": "Initial User",
                "request_reason": "Initial request",
                "items": [{"item_id": item_one.id, "quantity": "5.000"}],
            },
            format="json",
        )
        request_id = create_response.data["data"]["id"]

        update_response = self.client.put(
            f"/api/blending/store-requests/{request_id}/",
            {
                "remarks": "Updated request",
                "request_type": "ADDITIVE",
                "requested_for_name": "Shift Lead",
                "request_reason": "Need both additives",
                "items": [
                    {"item_id": item_one.id, "quantity": "7.000", "remarks": "Increase quantity"},
                    {"item_id": item_two.id, "quantity": "3.500", "remarks": "Add second item"},
                ],
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["data"]["requested_for_name"], "Shift Lead")
        self.assertEqual(len(update_response.data["data"]["items"]), 2)

        detail_response = self.client.get(f"/api/blending/store-requests/{request_id}/")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(len(detail_response.data["data"]["items"]), 2)
        self.assertEqual(detail_response.data["data"]["items"][0]["item"], item_one.id)
        self.assertEqual(detail_response.data["data"]["items"][1]["item"], item_two.id)

    def test_blending_stock_list_reads_store_inventory_for_blending_warehouse(self):
        item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Mixer Additive",
            unit="kg",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.blending_warehouse,
            quantity="10.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="BLEND-IN-1",
            created_by=self.store_user,
        )

        response = self.client.get("/api/blending/stock/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(response.data["data"]["results"][0]["quantity"], "10.000")

    def test_requestable_additive_stock_list_reads_store_inventory_for_dropdown(self):
        additive_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Processing Additive A",
            unit="kg",
        )
        non_additive_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="lldpe",
            item_name="LLDPE Resin",
            unit="kg",
        )
        apply_inward_stock(
            item=additive_item,
            warehouse=self.store_warehouse,
            quantity="25.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-ADD-1",
            created_by=self.store_user,
        )
        apply_inward_stock(
            item=non_additive_item,
            warehouse=self.store_warehouse,
            quantity="40.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-RM-1",
            created_by=self.store_user,
        )

        response = self.client.get("/api/blending/requestable-additive-stock/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 2)
        self.assertEqual(
            {row["item"] for row in response.data["data"]["results"]},
            {additive_item.id, non_additive_item.id},
        )
        self.assertEqual(
            {row["warehouse_code"] for row in response.data["data"]["results"]},
            {self.store_warehouse.code},
        )

    def test_blending_stock_list_supports_requestable_additive_scope(self):
        additive_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Mixer Additive",
            unit="kg",
        )
        non_additive_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="hdpe",
            item_name="Scope Resin",
            unit="kg",
        )
        apply_inward_stock(
            item=additive_item,
            warehouse=self.store_warehouse,
            quantity="15.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-ADD-2",
            created_by=self.store_user,
        )
        apply_inward_stock(
            item=non_additive_item,
            warehouse=self.store_warehouse,
            quantity="5.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-RM-2",
            created_by=self.store_user,
        )

        response = self.client.get("/api/blending/stock/?stock_scope=requestable")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 2)
        self.assertEqual(
            {row["item"] for row in response.data["data"]["results"]},
            {additive_item.id, non_additive_item.id},
        )
        self.assertEqual(
            {row["warehouse_code"] for row in response.data["data"]["results"]},
            {self.store_warehouse.code},
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
        request_response = self.client.post(
            "/api/blending/store-requests/",
            {"items": [{"item_id": item.id, "quantity": "2.000"}]},
            format="json",
        )
        request_id = request_response.data["data"]["id"]

        approve_response = self.client.post(
            f"/api/store/requests/{request_id}/approve/",
            {"approval_remarks": "Should not be allowed"},
            format="json",
        )

        self.assertEqual(approve_response.status_code, 403)
