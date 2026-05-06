from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.items.models import Item
from apps.store.models import StockRequest

from .models import BlendingStock


@override_settings(INTERNAL_API_KEY="test-internal-key")
class BlendingStockRequestTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="blending-user",
            password="test-pass-123",
        )
        access_token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    def test_request_stock_creates_pending_store_request(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="ldpe",
            item_name="Virgin LDPE",
            unit="kg",
        )

        response = self.client.post(
            "/api/blending/request-stock/",
            {
                "item_id": item.id,
                "quantity": "50.000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["request"]["status"], StockRequest.Status.PENDING)

        stock_request = StockRequest.objects.get(item=item)
        self.assertEqual(stock_request.quantity, Decimal("50.000"))
        self.assertEqual(stock_request.requested_by, self.user)

    def test_blending_stock_list_returns_items_with_positive_balance(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="mix",
            item_name="Mixer Resin",
            unit="kg",
        )
        BlendingStock.objects.create(
            item=item,
            quantity=Decimal("10.000"),
        )

        response = self.client.get("/api/blending/stock/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["item"], item.id)
        self.assertEqual(response.data[0]["quantity"], "10.000")
