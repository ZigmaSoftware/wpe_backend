from datetime import date
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.items.models import Item
from apps.production.models import BatchWeightEntry, BOMVariant, BOMVariantComponent, ProductionBatch, ProductionOutputCapture, ProductionOrder, ProductionOrderMaterialPlan
from apps.wpe_masters.models import ProductTypeCategory, ProductTypeSubtype, ProductionTypeMaster


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
            target_weight_grams="250.000",
            min_weight_grams="195.000",
            max_weight_grams="300.000",
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
                "production_for": "HSN - 500",
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
        self.assertEqual(order.production_for, "HSN - 500")
        self.assertEqual(material_plan.bom_variant_id, self.bom.id)
        self.assertEqual(material_plan.bom_component_id, self.component.id)
        self.assertEqual(str(material_plan.required_quantity), "150.000")
        self.assertEqual(str(material_plan.rate), "16.500")

        list_response = self.client.get("/api/production/production/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        rows = list_response.data["results"] if isinstance(list_response.data, dict) else list_response.data
        saved_row = next(
            row for row in rows if row["production_id"] == f"PO-MAT-{self.unique_suffix.upper()}"
        )
        self.assertEqual(saved_row["production_for"], "HSN - 500")

    def test_create_order_accepts_active_master_name_as_production_type(self):
        production_type = ProductionTypeMaster.objects.create(
            name=f"Granulation Production {self.unique_suffix}",
            is_active=True,
        )

        response = self.client.post(
            "/api/production/production/",
            {
                "production_id": f"PO-MASTER-{self.unique_suffix.upper()}",
                "production_type": production_type.name,
                "status": "PLANNED",
                "production_date": str(date.today()),
                "shift": "Shift 1 (6:00 am - 2:00 pm)",
                "planned_quantity": "50.000",
                "planned_weight": "0.000",
                "material_cost": "0.00",
                "total_cost": "0.00",
                "start_date_time": f"{date.today()}T06:00:00Z",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = ProductionOrder.objects.get(production_id=f"PO-MASTER-{self.unique_suffix.upper()}")
        self.assertEqual(order.production_type, production_type.name)


class ProductionBatchStageTransitionTests(APITestCase):
    def setUp(self):
        self.unique_suffix = uuid4().hex[:8]
        self.user = UserModel.objects.create_superuser(
            username=f"production-batch-{self.unique_suffix}",
            email=f"production-batch-{self.unique_suffix}@example.com",
            password="password123",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        self.item = Item.objects.create(
            category="Raw Material",
            group="Resin",
            sub_group="Primary",
            item_name=f"Blend Resin {self.unique_suffix}",
            unit="kgs",
        )
        self.bom = BOMVariant(variant_code=f"BOM-STAGE-{self.unique_suffix.upper()}", name="Stage Transition BOM")
        self.bom.set_password("secret123")
        self.bom.save()
        self.component = BOMVariantComponent.objects.create(
            bom_variant=self.bom,
            item=self.item,
            target_weight_grams="250.000",
            min_weight_grams="195.000",
            max_weight_grams="300.000",
            unit="kgs",
        )
        self.order = ProductionOrder.objects.create(
            production_id=f"PO-STAGE-{self.unique_suffix.upper()}",
            production_type="WPE Additive Production",
            production_date=date.today(),
        )

    def test_confirming_ad_batch_creates_pending_bl_batch_and_updates_order_type(self):
        create_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        batch_id = create_response.data["data"]["id"]
        weight_entry_id = create_response.data["data"]["weight_entries"][0]["id"]

        start_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{batch_id}/start/",
            format="json",
        )
        self.assertEqual(start_response.status_code, status.HTTP_200_OK)

        save_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{batch_id}/weights/{weight_entry_id}/",
            {"entered_weight_grams": "250.000"},
            format="json",
        )
        self.assertEqual(save_response.status_code, status.HTTP_200_OK)

        confirm_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{batch_id}/confirm/",
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        confirmed_batch = ProductionBatch.objects.get(pk=batch_id)
        self.assertEqual(confirmed_batch.status, ProductionBatch.BatchStatus.COMPLETED)
        self.assertIsNotNone(confirmed_batch.completed_at)

        next_batch = ProductionBatch.objects.get(production_order=self.order, stage=ProductionBatch.Stage.BL)
        self.assertEqual(next_batch.status, ProductionBatch.BatchStatus.PENDING)
        self.assertEqual(next_batch.bom_variant_id, self.bom.id)
        self.assertEqual(next_batch.weight_entries.count(), 1)

        output_capture = ProductionOutputCapture.objects.get(source_batch=confirmed_batch)
        self.assertEqual(output_capture.production_order_id, self.order.id)
        self.assertEqual(output_capture.binlot, confirmed_batch.batch_no)
        self.assertEqual(str(output_capture.weight_kg), "250.000")

        self.order.refresh_from_db()
        self.assertEqual(self.order.production_type, "WPE Blend Production")
        self.assertEqual(self.order.batch_number, next_batch.batch_no)

        stage_response = self.client.get("/api/production/stage-records/?stage=BL")
        self.assertEqual(stage_response.status_code, status.HTTP_200_OK)
        stage_rows = stage_response.data["data"]["results"]
        self.assertTrue(any(row["id"] == next_batch.id for row in stage_rows))

        output_response = self.client.get(f"/api/production/orders/{self.order.id}/output-captures/")
        self.assertEqual(output_response.status_code, status.HTTP_200_OK)
        output_rows = output_response.data["data"]
        self.assertEqual(len(output_rows), 1)
        self.assertEqual(output_rows[0]["source_batch"], confirmed_batch.id)
        self.assertEqual(output_rows[0]["source_batch_no"], confirmed_batch.batch_no)
        self.assertEqual(output_rows[0]["weight_kg"], "250.000")

    def test_ad_weight_validation_respects_component_unit_thresholds(self):
        self.component.target_weight_grams = "4.500"
        self.component.min_weight_grams = "4.400"
        self.component.max_weight_grams = "4.600"
        self.component.unit = "kgs"
        self.component.save()

        create_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        batch_id = create_response.data["data"]["id"]
        weight_entry_id = create_response.data["data"]["weight_entries"][0]["id"]

        start_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{batch_id}/start/",
            format="json",
        )
        self.assertEqual(start_response.status_code, status.HTTP_200_OK)

        save_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{batch_id}/weights/{weight_entry_id}/",
            {"entered_weight_grams": "4.500"},
            format="json",
        )

        self.assertEqual(save_response.status_code, status.HTTP_200_OK)
        self.assertEqual(save_response.data["message"], "Weight saved.")
        self.assertTrue(save_response.data["data"]["is_valid"])


class RecipeMasterApiTests(APITestCase):
    def setUp(self):
        self.unique_suffix = uuid4().hex[:8]
        self.user = UserModel.objects.create_superuser(
            username=f"recipe-admin-{self.unique_suffix}",
            email=f"recipe-admin-{self.unique_suffix}@example.com",
            password="password123",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_create_recipe_returns_201_and_is_available_in_lookup(self):
        response = self.client.post(
            "/api/production/recipes/",
            {
                "name": f"Recipe {self.unique_suffix}",
                "description": "Recipe notes",
                "recipe_version": "v1",
                "batch_size": "5.000",
                "batch_uom": "KG",
                "status": "DRAFT",
                "approved_by": None,
                "approved_at": None,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        recipe_id = response.data["id"]
        self.assertTrue(response.data["code"].startswith("REC"))

        lookup_response = self.client.get("/api/production/recipes/lookup/")

        self.assertEqual(lookup_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(row["id"] == recipe_id for row in lookup_response.data))
