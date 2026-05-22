from datetime import date
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.production.models import BOMVariant, BOMVariantComponent, BatchWeightEntry, ProductionOrder
from apps.wpe_masters.models import ProductTypeCategory, ProductTypeSubtype


UserModel = get_user_model()


class BOMVariantSubtypeMappingTests(APITestCase):
    def setUp(self):
        self.unique_suffix = uuid4().hex[:8]
        self.user = UserModel.objects.create_superuser(
            username=f"production-admin-{self.unique_suffix}",
            email=f"production-admin-{self.unique_suffix}@example.com",
            password="password123",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        self.category = ProductTypeCategory.objects.create(
            name=f"Chemicals {self.unique_suffix}",
            description="Chemical additives",
            sort_order=10,
            is_active=True,
        )
        self.adhesive = ProductTypeSubtype.objects.create(
            category=self.category,
            name="Adhesive",
            description="Adhesive component",
            sort_order=10,
            is_active=True,
        )
        self.resin = ProductTypeSubtype.objects.create(
            category=self.category,
            name="Resin",
            description="Resin component",
            sort_order=20,
            is_active=True,
        )

        self.bom = BOMVariant(variant_code=f"BOM-{self.unique_suffix.upper()}", name="Chemical Blend")
        self.bom.set_password("secret123")
        self.bom.save()

        self.components_url = f"/api/production/bom-variants/{self.bom.id}/components/"

    def test_bulk_save_persists_subtype_components(self):
        response = self.client.put(
            self.components_url,
            {
                "components": [
                    {
                        "product_subtype": self.adhesive.id,
                        "target_weight_grams": "250.000",
                        "min_weight_grams": "195.000",
                        "max_weight_grams": "9205.000",
                        "unit": "g",
                    },
                    {
                        "product_subtype": self.resin.id,
                        "target_weight_grams": "150.000",
                        "min_weight_grams": "195.000",
                        "max_weight_grams": "9205.000",
                        "unit": "g",
                    },
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(BOMVariantComponent.objects.filter(bom_variant=self.bom).count(), 2)

        saved_components = response.data["data"]["components"]
        self.assertEqual(saved_components[0]["item_name"], "Adhesive")
        self.assertEqual(saved_components[0]["item_code"], self.adhesive.code)
        self.assertEqual(saved_components[0]["category"], self.category.name)
        self.assertEqual(saved_components[0]["source_type"], "PRODUCT_SUBTYPE")
        self.assertIsNone(saved_components[0]["item"])
        self.assertEqual(saved_components[0]["product_subtype"], self.adhesive.id)

    def test_bulk_save_rejects_duplicate_subtypes(self):
        response = self.client.put(
            self.components_url,
            {
                "components": [
                    {
                        "product_subtype": self.adhesive.id,
                        "target_weight_grams": "250.000",
                        "unit": "g",
                    },
                    {
                        "product_subtype": self.adhesive.id,
                        "target_weight_grams": "150.000",
                        "unit": "g",
                    },
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("duplicate component selection", response.data["message"].lower())
        self.assertFalse(BOMVariantComponent.objects.filter(bom_variant=self.bom).exists())

    def test_batch_creation_uses_saved_subtype_components(self):
        self.client.put(
            self.components_url,
            {
                "components": [
                    {
                        "product_subtype": self.adhesive.id,
                        "target_weight_grams": "250.000",
                        "unit": "g",
                    },
                    {
                        "product_subtype": self.resin.id,
                        "target_weight_grams": "150.000",
                        "unit": "g",
                    },
                ]
            },
            format="json",
        )

        order = ProductionOrder.objects.create(
            production_id=f"PO-{self.unique_suffix.upper()}",
            production_date=date.today(),
        )

        response = self.client.post(
            f"/api/production/orders/{order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        weight_entries = response.data["data"]["weight_entries"]
        self.assertEqual(len(weight_entries), 2)
        self.assertEqual({entry["item_name"] for entry in weight_entries}, {"Adhesive", "Resin"})
        self.assertTrue(all(entry["source_type"] == "PRODUCT_SUBTYPE" for entry in weight_entries))
        self.assertTrue(all(entry["item"] is None for entry in weight_entries))
        self.assertEqual(BatchWeightEntry.objects.filter(batch_id=response.data["data"]["id"], item__isnull=True).count(), 2)
