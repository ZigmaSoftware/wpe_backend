from datetime import date
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.items.models import Item
from apps.production.models import BOMVariant, BOMVariantComponent, BatchWeightEntry, ProductionOrder, ProductionOrderMaterialPlan
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

    def test_create_variant_without_password_is_allowed(self):
        response = self.client.post(
            "/api/production/bom-variants/",
            {
                "variant_code": f"BOM-NOPASS-{self.unique_suffix.upper()}",
                "name": "Passwordless BOM",
                "components": [
                    {
                        "product_subtype": self.adhesive.id,
                        "target_weight_grams": "250.000",
                        "unit": "g",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["data"]["has_password"])

    def test_recipe_endpoint_allows_passwordless_variant(self):
        response = self.client.post(
            "/api/production/bom-variants/",
            {
                "variant_code": f"BOM-OPEN-{self.unique_suffix.upper()}",
                "name": "Open Recipe BOM",
                "components": [
                    {
                        "product_subtype": self.adhesive.id,
                        "target_weight_grams": "250.000",
                        "unit": "g",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        bom_id = response.data["data"]["id"]

        recipe_response = self.client.post(
            f"/api/production/bom-variants/{bom_id}/recipe/",
            {},
            format="json",
        )

        self.assertEqual(recipe_response.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe_response.data["data"]["id"], bom_id)
        self.assertFalse(recipe_response.data["data"]["has_password"])

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


class ProductionOrderMaterialPlanTests(APITestCase):
    def setUp(self):
        self.unique_suffix = uuid4().hex[:8]
        self.user = UserModel.objects.create_superuser(
            username=f"production-planner-{self.unique_suffix}",
            email=f"production-planner-{self.unique_suffix}@example.com",
            password="password123",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        self.item = Item.objects.create(
            category="Raw Material",
            group="Resin",
            sub_group="Primary",
            item_name=f"HDPE Resin {self.unique_suffix}",
            unit="kgs",
        )
        self.fg_item = Item.objects.create(
            category="Finished Goods",
            group="Blend",
            sub_group="WPE",
            item_name=f"Finished Blend {self.unique_suffix}",
            unit="kgs",
        )
        self.category = ProductTypeCategory.objects.create(
            name=f"Category {self.unique_suffix}",
            description="Category",
            sort_order=1,
            is_active=True,
        )
        self.subtype = ProductTypeSubtype.objects.create(
            category=self.category,
            name=f"Subtype {self.unique_suffix}",
            description="Subtype",
            sort_order=1,
            is_active=True,
        )
        self.bom = BOMVariant(variant_code=f"BOM-MAT-{self.unique_suffix.upper()}", name="Material Plan BOM", product_item=self.fg_item)
        self.bom.set_password("secret123")
        self.bom.save()
        self.component = BOMVariantComponent.objects.create(
            bom_variant=self.bom,
            item=self.item,
            target_weight_grams="1.500",
            min_weight_grams="1.000",
            max_weight_grams="2.000",
            unit="kgs",
        )

    def test_bom_variant_list_can_filter_by_product_item(self):
        response = self.client.get(f"/api/production/bom-variants/?product_item={self.fg_item.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        variants = response.data["data"]
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["id"], self.bom.id)

    def test_create_order_can_persist_material_plans(self):
        response = self.client.post(
            "/api/production/production/",
            {
                "production_id": f"PO-MAT-{self.unique_suffix.upper()}",
                "production_type": "RECYCLING_PRODUCTION",
                "status": "PLANNED",
                "production_date": str(date.today()),
                "shift": "Shift 1 (6:00 am - 2:00 pm)",
                "planned_quantity": "100.000",
                "planned_weight": "0.000",
                "material_cost": "2500.00",
                "total_cost": "2500.00",
                "start_date_time": f"{date.today()}T06:00:00Z",
                "materials": [
                    {
                        "sequence": 1,
                        "source_type": "ITEM",
                        "is_bom_derived": True,
                        "is_manual": False,
                        "bom_variant": self.bom.id,
                        "bom_component": self.component.id,
                        "item": self.item.id,
                        "item_code": self.item.item_code,
                        "item_name": self.item.item_name,
                        "unit": "kgs",
                        "per_unit_quantity": "1.500",
                        "bom_quantity": "150.000",
                        "required_quantity": "150.000",
                        "received_quantity": "10.000",
                        "remaining_quantity": "140.000",
                        "request_quantity": "140.000",
                        "rate": "16.500",
                        "amount": "2475.00",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = ProductionOrder.objects.get(production_id=f"PO-MAT-{self.unique_suffix.upper()}")
        material_plan = ProductionOrderMaterialPlan.objects.get(production_order=order)
        self.assertEqual(material_plan.bom_variant_id, self.bom.id)
        self.assertEqual(material_plan.bom_component_id, self.component.id)
        self.assertEqual(str(material_plan.required_quantity), "150.000")
        self.assertEqual(str(material_plan.rate), "16.500")
