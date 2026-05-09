from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.admin_master.models import Staff, UserCreation, UserType
from apps.items.models import Item
from apps.store.models import StockRequest, StoreTransaction
from apps.store.services import apply_inward_stock, get_blending_warehouse


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

    def test_request_stock_creates_pending_store_request_with_header_and_items(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="ldpe",
            item_name="Virgin LDPE",
            unit="kg",
        )

        response = self.client.post(
            "/api/blending/store-requests/",
            {
                "remarks": "Need material for mixing line 1",
                "items": [
                    {
                        "item_id": item.id,
                        "quantity": "50.000",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["status"], StockRequest.Status.PENDING)
        self.assertTrue(response.data["data"]["request_no"].startswith("SR-"))
        self.assertEqual(len(response.data["data"]["items"]), 1)

        stock_request = StockRequest.objects.prefetch_related("items").get(pk=response.data["data"]["id"])
        self.assertEqual(stock_request.requested_by, self.blending_user)
        self.assertEqual(stock_request.items.first().requested_qty, 50)

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

    def test_blending_stock_list_reads_store_inventory_for_blending_warehouse(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="mix",
            item_name="Mixer Resin",
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
        self.assertEqual(response.data["data"]["results"][0]["item"], item.id)
        self.assertEqual(response.data["data"]["results"][0]["available_qty"], "10.000")
