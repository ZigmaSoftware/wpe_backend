from datetime import date
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.items.models import Item
from apps.production.models import BagCreationMaster, BatchWeightEntry, BinCreationMaster, BOMVariant, BOMVariantComponent, ProductionBatch, ProductionOutputCapture, ProductionOrder, ProductionOrderMaterialPlan
from apps.wpe_masters.models import ProductTypeCategory, ProductTypeSubtype, ProductionTypeMaster


UserModel = get_user_model()
SCANCODE_TIME_ZONE = ZoneInfo("Asia/Kolkata")


def format_scancode_time(value):
    return timezone.localtime(value, SCANCODE_TIME_ZONE).strftime("%d%m%Y%H%M")


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
                        "min_weight_grams": "100.000",
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

    def test_recipe_item_weight_edit_preserves_component_used_by_batch_weights(self):
        component = BOMVariantComponent.objects.create(
            bom_variant=self.bom,
            product_subtype=self.adhesive,
            target_weight_grams="250.000",
            min_weight_grams="195.000",
            max_weight_grams="9205.000",
            unit="g",
        )
        order = ProductionOrder.objects.create(
            production_id=f"PO-EDIT-{self.unique_suffix.upper()}",
            production_type="BLENDING_PRODUCTION",
            production_date=date.today(),
        )
        batch = ProductionBatch.objects.create(
            batch_no=f"BATCH-EDIT-{self.unique_suffix.upper()}",
            production_order=order,
            bom_variant=self.bom,
            stage=ProductionBatch.Stage.AD,
        )
        BatchWeightEntry.objects.create(
            batch=batch,
            bom_component=component,
            target_weight_grams="250.000",
        )

        response = self.client.put(
            f"/api/production/recipes/{self.bom.id}/items/",
            {
                "components": [
                    {
                        "id": component.id,
                        "product_subtype": self.adhesive.id,
                        "target_weight_grams": "275.000",
                        "min_weight_grams": "200.000",
                        "max_weight_grams": "9000.000",
                        "unit": "g",
                    },
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        component.refresh_from_db()
        self.assertEqual(str(component.target_weight_grams), "275.000")
        self.assertEqual(str(component.min_weight_grams), "200.000")
        self.assertEqual(BOMVariantComponent.objects.filter(bom_variant=self.bom).count(), 1)
        self.assertEqual(response.data["components"][0]["id"], component.id)

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
                        "target_weight_grams": "250.000",
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
                        "min_weight_grams": "100.000",
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
                "extra_form_data": {
                    "production_facility": "10",
                    "work_center": "20",
                    "shift_incharge": "30",
                    "selected_bom_variant_id": str(self.bom.id),
                    "bom_multiplier": "2",
                },
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
        self.assertEqual(order.extra_form_data["production_facility"], "10")
        self.assertEqual(order.extra_form_data["work_center"], "20")
        self.assertEqual(order.extra_form_data["selected_bom_variant_id"], str(self.bom.id))
        self.assertEqual(material_plan.bom_variant_id, self.bom.id)
        self.assertEqual(material_plan.bom_component_id, self.component.id)
        self.assertEqual(str(material_plan.required_quantity), "150.000")
        self.assertEqual(str(material_plan.rate), "16.500")

        detail_response = self.client.get(f"/api/production/production/{order.id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        detail_data = detail_response.data["data"] if isinstance(detail_response.data, dict) and "data" in detail_response.data else detail_response.data
        self.assertEqual(detail_data["extra_form_data"]["work_center"], "20")
        self.assertEqual(detail_data["extra_form_data"]["selected_bom_variant_id"], str(self.bom.id))

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
        self.primary_free_bin = BinCreationMaster.objects.create(
            code=f"BIN-{self.unique_suffix.upper()}-A",
            name=f"Primary Free Bin {self.unique_suffix}",
            current_status=BinCreationMaster.BinStatus.FREE,
            is_active=True,
        )
        self.secondary_free_bin = BinCreationMaster.objects.create(
            code=f"BIN-{self.unique_suffix.upper()}-B",
            name=f"Secondary Free Bin {self.unique_suffix}",
            current_status=BinCreationMaster.BinStatus.FREE,
            is_active=True,
        )
        self.primary_free_bag = BagCreationMaster.objects.create(
            code=f"BAG-{self.unique_suffix.upper()}-A",
            name=f"Primary Free Bag {self.unique_suffix}",
            current_status=BagCreationMaster.BagStatus.FREE,
            is_active=True,
        )
        self.secondary_free_bag = BagCreationMaster.objects.create(
            code=f"BAG-{self.unique_suffix.upper()}-B",
            name=f"Secondary Free Bag {self.unique_suffix}",
            current_status=BagCreationMaster.BagStatus.FREE,
            is_active=True,
        )

    def test_ad_batch_numbers_use_prd_id_prefix_and_restart_per_order(self):
        first_order = ProductionOrder.objects.create(
            production_id="01",
            production_type="WPE Additive Production",
            production_date=date.today(),
        )
        second_order = ProductionOrder.objects.create(
            production_id="02",
            production_type="WPE Additive Production",
            production_date=date.today(),
        )

        first_order_first_batch = self.client.post(
            f"/api/production/orders/{first_order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )
        self.assertEqual(first_order_first_batch.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first_order_first_batch.data["data"]["batch_no"], "BATCH01-0001")
        self.assertEqual(first_order_first_batch.data["data"]["display_batch_no"], "BATCH01-0001")

        first_order_second_batch = self.client.post(
            f"/api/production/orders/{first_order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )
        self.assertEqual(first_order_second_batch.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first_order_second_batch.data["data"]["batch_no"], "BATCH01-0002")
        self.assertEqual(first_order_second_batch.data["data"]["display_batch_no"], "BATCH01-0002")

        second_order_first_batch = self.client.post(
            f"/api/production/orders/{second_order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )
        self.assertEqual(second_order_first_batch.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_order_first_batch.data["data"]["batch_no"], "BATCH02-0001")
        self.assertEqual(second_order_first_batch.data["data"]["display_batch_no"], "BATCH02-0001")

    def test_ad_batch_with_multiple_small_decimal_components_confirms_successfully(self):
        self.order.production_id = "10"
        self.order.save(update_fields=["production_id"])

        self.component.target_weight_grams = "4.400"
        self.component.min_weight_grams = "4.300"
        self.component.max_weight_grams = "4.500"
        self.component.unit = "g"
        self.component.save()

        second_item = Item.objects.create(
            category="Raw Material",
            group="Additives",
            sub_group="Secondary",
            item_name=f"Two Pole {self.unique_suffix}",
            unit="kgs",
        )
        third_item = Item.objects.create(
            category="Raw Material",
            group="Additives",
            sub_group="Tertiary",
            item_name=f"Third Pole {self.unique_suffix}",
            unit="kgs",
        )
        BOMVariantComponent.objects.create(
            bom_variant=self.bom,
            item=second_item,
            target_weight_grams="4.400",
            min_weight_grams="4.300",
            max_weight_grams="4.500",
            unit="g",
            sequence=2,
        )
        BOMVariantComponent.objects.create(
            bom_variant=self.bom,
            item=third_item,
            target_weight_grams="4.500",
            min_weight_grams="4.400",
            max_weight_grams="4.600",
            unit="g",
            sequence=3,
        )

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
        weight_entries = create_response.data["data"]["weight_entries"]
        self.assertEqual(len(weight_entries), 3)

        start_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{batch_id}/start/",
            format="json",
        )
        self.assertEqual(start_response.status_code, status.HTTP_200_OK)

        entered_weights = ["4.400", "4.400", "4.500"]
        for entry, entered_weight in zip(weight_entries, entered_weights):
            save_response = self.client.post(
                f"/api/production/orders/{self.order.id}/batches/{batch_id}/weights/{entry['id']}/",
                {"entered_weight_grams": entered_weight},
                format="json",
            )
            self.assertEqual(save_response.status_code, status.HTTP_200_OK)
            self.assertTrue(save_response.data["data"]["is_valid"])

        confirm_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{batch_id}/confirm/",
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        confirmed_batch = ProductionBatch.objects.get(pk=batch_id)
        self.assertEqual(confirmed_batch.status, ProductionBatch.BatchStatus.COMPLETED)
        self.assertFalse(BatchWeightEntry.objects.filter(batch_id=batch_id, is_valid=False).exists())
        self.assertEqual(BatchWeightEntry.objects.filter(batch_id=batch_id, is_valid=True).count(), 3)

        next_batch = ProductionBatch.objects.get(production_order=self.order, stage=ProductionBatch.Stage.BL)
        self.assertEqual(next_batch.status, ProductionBatch.BatchStatus.IN_PROGRESS)

    def test_confirming_ad_batch_creates_bl_handoff_without_followup_ad_batch(self):
        self.order.production_id = "01"
        self.order.save(update_fields=["production_id"])

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
        self.assertEqual(next_batch.status, ProductionBatch.BatchStatus.IN_PROGRESS)
        self.assertEqual(next_batch.bom_variant_id, self.bom.id)
        self.assertEqual(next_batch.weight_entries.count(), 1)
        self.assertEqual(next_batch.workflow_batch_no, confirmed_batch.batch_no)
        self.assertEqual(next_batch.started_at, confirmed_batch.completed_at)

        self.assertFalse(
            ProductionBatch.objects.filter(
                production_order=self.order,
                stage=ProductionBatch.Stage.AD,
                status__in=[ProductionBatch.BatchStatus.PENDING, ProductionBatch.BatchStatus.IN_PROGRESS],
            ).exclude(pk=confirmed_batch.pk).exists()
        )

        output_capture = ProductionOutputCapture.objects.get(source_batch=confirmed_batch)
        self.assertEqual(output_capture.production_order_id, self.order.id)
        self.assertEqual(output_capture.binlot, confirmed_batch.batch_no)
        self.assertEqual(str(output_capture.weight_kg), "250.000")
        expected_ad_scancode = f"01AD{format_scancode_time(output_capture.captured_at)}01"
        self.assertEqual(output_capture.scancode_id, expected_ad_scancode)

        self.order.refresh_from_db()
        self.assertEqual(self.order.production_type, "WPE Additive Production")
        self.assertEqual(self.order.batch_number, confirmed_batch.batch_no)

        ad_stage_response = self.client.get("/api/production/stage-records/?stage=AD")
        self.assertEqual(ad_stage_response.status_code, status.HTTP_200_OK)
        ad_stage_rows = ad_stage_response.data["data"]["results"]
        matched_ad_row = next(row for row in ad_stage_rows if row["order_id"] == self.order.id)
        self.assertEqual(matched_ad_row["production_type"], "WPE Additive Production")
        self.assertEqual(matched_ad_row["batch_count"], 1)
        self.assertEqual(matched_ad_row["workflow_status"], "BL")

        bl_stage_response = self.client.get("/api/production/stage-records/?stage=BL")
        self.assertEqual(bl_stage_response.status_code, status.HTTP_200_OK)
        bl_stage_rows = bl_stage_response.data["data"]["results"]
        matched_bl_row = next(row for row in bl_stage_rows if row["order_id"] == self.order.id)
        self.assertEqual(matched_bl_row["production_type"], "WPE Blend Production")
        self.assertEqual(matched_bl_row["batch_count"], 1)
        self.assertEqual(matched_bl_row["batch_no"], confirmed_batch.batch_no)
        self.assertEqual(matched_bl_row["display_batch_no"], confirmed_batch.batch_no)
        self.assertEqual(matched_bl_row["workflow_status"], "BL")

        ad_batch_response = self.client.get(
            f"/api/production/orders/{self.order.id}/batches/",
            {"stage": "AD"},
        )
        self.assertEqual(ad_batch_response.status_code, status.HTTP_200_OK)
        ad_batches = ad_batch_response.data["data"]
        completed_ad_row = next(row for row in ad_batches if row["id"] == confirmed_batch.id)
        self.assertEqual(completed_ad_row["display_status"], "BL - Blending")
        self.assertEqual(len(ad_batches), 1)

        output_response = self.client.get(f"/api/production/orders/{self.order.id}/output-captures/")
        self.assertEqual(output_response.status_code, status.HTTP_200_OK)
        output_rows = output_response.data["data"]
        self.assertEqual(len(output_rows), 1)
        self.assertEqual(output_rows[0]["source_batch"], confirmed_batch.id)
        self.assertEqual(output_rows[0]["source_batch_no"], confirmed_batch.batch_no)
        self.assertEqual(output_rows[0]["weight_kg"], "250.000")
        self.assertEqual(output_rows[0]["scancode_id"], expected_ad_scancode)

    def test_bl_output_capture_moves_batch_to_gl_and_reuses_single_capture_record(self):
        self.order.production_id = "01"
        self.order.save(update_fields=["production_id"])

        create_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        ad_batch_id = create_response.data["data"]["id"]
        weight_entry_id = create_response.data["data"]["weight_entries"][0]["id"]

        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/start/",
            format="json",
        )
        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/weights/{weight_entry_id}/",
            {"entered_weight_grams": "250.000"},
            format="json",
        )
        confirm_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/confirm/",
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        ad_batch = ProductionBatch.objects.get(pk=ad_batch_id)
        ad_capture = ProductionOutputCapture.objects.get(source_batch=ad_batch)
        expected_ad_scancode = f"01AD{format_scancode_time(ad_capture.captured_at)}01"
        self.assertEqual(ad_capture.scancode_id, expected_ad_scancode)

        bl_batch = ProductionBatch.objects.get(production_order=self.order, stage=ProductionBatch.Stage.BL)

        capture_response = self.client.post(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {
                "source_batch": bl_batch.id,
                "weight_kg": "180.500",
            },
            format="json",
        )
        self.assertEqual(capture_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(capture_response.data["data"]["source_batch"], bl_batch.id)
        self.assertEqual(capture_response.data["data"]["weight_kg"], "180.500")
        self.assertEqual(capture_response.data["data"]["component_columns"][0]["label"], "Bin Weight")
        self.assertFalse(capture_response.data["data"]["is_outwarded"])

        stored_capture = ProductionOutputCapture.objects.get(source_batch=bl_batch)
        self.assertEqual(stored_capture.production_order_id, self.order.id)
        self.assertEqual(str(stored_capture.weight_kg), "180.500")
        self.assertEqual(stored_capture.binlot, self.primary_free_bin.code)
        expected_scancode = f"01BL{format_scancode_time(stored_capture.captured_at)}01"
        self.assertEqual(stored_capture.scancode_id, expected_scancode)
        self.assertEqual(capture_response.data["data"]["scancode_id"], expected_scancode)

        bl_batch.refresh_from_db()
        self.assertEqual(bl_batch.status, ProductionBatch.BatchStatus.IN_PROGRESS)
        self.assertFalse(
            ProductionBatch.objects.filter(
                production_order=self.order,
                stage=ProductionBatch.Stage.GL,
            ).exists()
        )

        self.primary_free_bin.refresh_from_db()
        self.secondary_free_bin.refresh_from_db()
        self.assertEqual(self.primary_free_bin.current_status, BinCreationMaster.BinStatus.OCCUPIED)
        self.assertEqual(self.secondary_free_bin.current_status, BinCreationMaster.BinStatus.FREE)

        filtered_output_response = self.client.get(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {"source_batch": bl_batch.id},
        )
        self.assertEqual(filtered_output_response.status_code, status.HTTP_200_OK)
        filtered_rows = filtered_output_response.data["data"]
        self.assertEqual(len(filtered_rows), 1)
        self.assertEqual(filtered_rows[0]["source_batch"], bl_batch.id)
        self.assertEqual(filtered_rows[0]["weight_kg"], "180.500")
        self.assertEqual(filtered_rows[0]["details"][0]["item_name"], "Bin Weight")
        self.assertFalse(filtered_rows[0]["is_outwarded"])

        confirm_bl_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{bl_batch.id}/confirm/",
            format="json",
        )
        self.assertEqual(confirm_bl_response.status_code, status.HTTP_200_OK)

        bl_batch.refresh_from_db()
        self.assertEqual(bl_batch.status, ProductionBatch.BatchStatus.COMPLETED)
        self.assertIsNotNone(bl_batch.completed_at)

        stored_capture.refresh_from_db()
        self.primary_free_bin.refresh_from_db()
        self.secondary_free_bin.refresh_from_db()
        self.assertEqual(self.primary_free_bin.current_status, BinCreationMaster.BinStatus.FREE)
        self.assertEqual(self.secondary_free_bin.current_status, BinCreationMaster.BinStatus.FREE)

        gl_batch = ProductionBatch.objects.get(production_order=self.order, stage=ProductionBatch.Stage.GL)
        self.assertEqual(gl_batch.status, ProductionBatch.BatchStatus.IN_PROGRESS)
        self.assertEqual(gl_batch.workflow_batch_no, bl_batch.workflow_batch_no)
        self.assertEqual(gl_batch.started_at, bl_batch.completed_at)

        bl_batches_response = self.client.get(
            f"/api/production/orders/{self.order.id}/batches/",
            {"stage": "BL"},
        )
        self.assertEqual(bl_batches_response.status_code, status.HTTP_200_OK)
        bl_batches = bl_batches_response.data["data"]
        completed_bl_row = next(row for row in bl_batches if row["id"] == bl_batch.id)
        self.assertEqual(completed_bl_row["display_status"], "GL - Granulation")
        self.assertEqual(completed_bl_row["total_weight_grams"], 180.5)

        bl_stage_response = self.client.get("/api/production/stage-records/?stage=BL")
        self.assertEqual(bl_stage_response.status_code, status.HTTP_200_OK)
        bl_stage_rows = bl_stage_response.data["data"]["results"]
        matched_bl_row = next(row for row in bl_stage_rows if row["order_id"] == self.order.id)
        self.assertEqual(matched_bl_row["workflow_status"], "GL")

        post_outward_output_response = self.client.get(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {"source_batch": bl_batch.id},
        )
        self.assertEqual(post_outward_output_response.status_code, status.HTTP_200_OK)
        post_outward_rows = post_outward_output_response.data["data"]
        self.assertEqual(len(post_outward_rows), 1)
        self.assertTrue(post_outward_rows[0]["is_outwarded"])

        ad_output_response = self.client.get(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {"source_batch": ad_batch_id},
        )
        self.assertEqual(ad_output_response.status_code, status.HTTP_200_OK)
        ad_output_rows = ad_output_response.data["data"]
        self.assertEqual(len(ad_output_rows), 1)
        self.assertEqual(ad_output_rows[0]["source_batch"], ad_batch_id)
        self.assertEqual(ad_output_rows[0]["scancode_id"], expected_ad_scancode)

        ad_batches_response = self.client.get(
            f"/api/production/orders/{self.order.id}/batches/",
            {"stage": "AD"},
        )
        self.assertEqual(ad_batches_response.status_code, status.HTTP_200_OK)
        ad_batches = ad_batches_response.data["data"]
        completed_ad_row = next(row for row in ad_batches if row["batch_no"] == bl_batch.workflow_batch_no)
        self.assertEqual(completed_ad_row["display_status"], "GL - Granulation")

        repeat_capture_response = self.client.post(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {
                "source_batch": bl_batch.id,
                "weight_kg": "181.250",
            },
            format="json",
        )
        self.assertEqual(repeat_capture_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            repeat_capture_response.data["message"],
            "Output capture already exists for this batch.",
        )
        self.assertEqual(
            ProductionOutputCapture.objects.filter(source_batch=bl_batch).count(),
            1,
        )
        stored_capture.refresh_from_db()
        self.assertEqual(str(stored_capture.weight_kg), "180.500")

    def test_deleting_ad_workflow_batch_removes_related_batches_and_releases_reserved_bin(self):
        create_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        ad_batch_id = create_response.data["data"]["id"]
        weight_entry_id = create_response.data["data"]["weight_entries"][0]["id"]

        self.assertEqual(
            self.client.post(
                f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/start/",
                format="json",
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(
                f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/weights/{weight_entry_id}/",
                {"entered_weight_grams": "250.000"},
                format="json",
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(
                f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/confirm/",
                format="json",
            ).status_code,
            status.HTTP_200_OK,
        )

        bl_batch = ProductionBatch.objects.get(production_order=self.order, stage=ProductionBatch.Stage.BL)
        capture_response = self.client.post(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {
                "source_batch": bl_batch.id,
                "weight_kg": "4.000",
            },
            format="json",
        )
        self.assertEqual(capture_response.status_code, status.HTTP_201_CREATED)

        bl_capture = ProductionOutputCapture.objects.get(source_batch=bl_batch)
        reserved_bin = BinCreationMaster.objects.get(code=bl_capture.binlot)
        self.assertEqual(reserved_bin.current_status, BinCreationMaster.BinStatus.OCCUPIED)

        delete_response = self.client.delete(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/",
            format="json",
        )
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)

        self.assertFalse(ProductionBatch.objects.filter(pk=ad_batch_id).exists())
        self.assertFalse(ProductionBatch.objects.filter(pk=bl_batch.id).exists())
        self.assertFalse(ProductionOutputCapture.objects.filter(source_batch_id=bl_batch.id).exists())

        reserved_bin.refresh_from_db()
        self.assertEqual(reserved_bin.current_status, BinCreationMaster.BinStatus.FREE)

        self.order.refresh_from_db()
        self.assertFalse(self.order.batch_number)

    def test_gl_output_capture_assigns_free_bag_and_marks_it_occupied(self):
        self.order.production_id = "01"
        self.order.save(update_fields=["production_id"])

        create_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        ad_batch_id = create_response.data["data"]["id"]
        weight_entry_id = create_response.data["data"]["weight_entries"][0]["id"]

        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/start/",
            format="json",
        )
        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/weights/{weight_entry_id}/",
            {"entered_weight_grams": "250.000"},
            format="json",
        )
        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/confirm/",
            format="json",
        )

        bl_batch = ProductionBatch.objects.get(production_order=self.order, stage=ProductionBatch.Stage.BL)
        self.client.post(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {
                "source_batch": bl_batch.id,
                "weight_kg": "180.500",
            },
            format="json",
        )
        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{bl_batch.id}/confirm/",
            format="json",
        )

        gl_batch = ProductionBatch.objects.get(production_order=self.order, stage=ProductionBatch.Stage.GL)

        capture_response = self.client.post(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {
                "source_batch": gl_batch.id,
                "weight_kg": "25.000",
            },
            format="json",
        )
        self.assertEqual(capture_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(capture_response.data["data"]["source_batch"], gl_batch.id)
        self.assertEqual(capture_response.data["data"]["weight_kg"], "25.000")
        self.assertEqual(capture_response.data["data"]["binlot"], self.primary_free_bag.code)
        self.assertEqual(capture_response.data["data"]["component_columns"][0]["label"], "Bag Weight")

        stored_capture = ProductionOutputCapture.objects.get(source_batch=gl_batch)
        self.assertEqual(stored_capture.production_order_id, self.order.id)
        self.assertEqual(str(stored_capture.weight_kg), "25.000")
        self.assertEqual(stored_capture.binlot, self.primary_free_bag.code)
        expected_scancode = f"01GL{format_scancode_time(stored_capture.captured_at)}01"
        self.assertEqual(stored_capture.scancode_id, expected_scancode)
        self.assertEqual(capture_response.data["data"]["scancode_id"], expected_scancode)

        self.primary_free_bag.refresh_from_db()
        self.secondary_free_bag.refresh_from_db()
        self.assertEqual(self.primary_free_bag.current_status, BagCreationMaster.BagStatus.OCCUPIED)
        self.assertEqual(self.secondary_free_bag.current_status, BagCreationMaster.BagStatus.FREE)

        filtered_output_response = self.client.get(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {"source_batch": gl_batch.id},
        )
        self.assertEqual(filtered_output_response.status_code, status.HTTP_200_OK)
        filtered_rows = filtered_output_response.data["data"]
        self.assertEqual(len(filtered_rows), 1)
        self.assertEqual(filtered_rows[0]["source_batch"], gl_batch.id)
        self.assertEqual(filtered_rows[0]["binlot"], self.primary_free_bag.code)
        self.assertEqual(filtered_rows[0]["details"][0]["item_name"], "Bag Weight")

    def test_gl_outward_moves_batch_to_pr_and_releases_assigned_bag(self):
        create_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        ad_batch_id = create_response.data["data"]["id"]
        weight_entry_id = create_response.data["data"]["weight_entries"][0]["id"]

        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/start/",
            format="json",
        )
        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/weights/{weight_entry_id}/",
            {"entered_weight_grams": "250.000"},
            format="json",
        )
        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/confirm/",
            format="json",
        )

        bl_batch = ProductionBatch.objects.get(production_order=self.order, stage=ProductionBatch.Stage.BL)
        self.client.post(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {
                "source_batch": bl_batch.id,
                "weight_kg": "180.500",
            },
            format="json",
        )
        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{bl_batch.id}/confirm/",
            format="json",
        )

        gl_batch = ProductionBatch.objects.get(production_order=self.order, stage=ProductionBatch.Stage.GL)

        capture_response = self.client.post(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {
                "source_batch": gl_batch.id,
                "weight_kg": "25.000",
            },
            format="json",
        )
        self.assertEqual(capture_response.status_code, status.HTTP_201_CREATED)

        confirm_gl_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{gl_batch.id}/confirm/",
            format="json",
        )
        self.assertEqual(confirm_gl_response.status_code, status.HTTP_200_OK)

        gl_batch.refresh_from_db()
        self.assertEqual(gl_batch.status, ProductionBatch.BatchStatus.COMPLETED)
        self.assertIsNotNone(gl_batch.completed_at)

        self.primary_free_bag.refresh_from_db()
        self.secondary_free_bag.refresh_from_db()
        self.assertEqual(self.primary_free_bag.current_status, BagCreationMaster.BagStatus.FREE)
        self.assertEqual(self.secondary_free_bag.current_status, BagCreationMaster.BagStatus.FREE)

        filtered_output_response = self.client.get(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {"source_batch": gl_batch.id},
        )
        self.assertEqual(filtered_output_response.status_code, status.HTTP_200_OK)
        filtered_rows = filtered_output_response.data["data"]
        self.assertEqual(len(filtered_rows), 1)
        self.assertTrue(filtered_rows[0]["is_outwarded"])
        self.assertEqual(filtered_rows[0]["binlot"], self.primary_free_bag.code)

        gl_batches_response = self.client.get(
            f"/api/production/orders/{self.order.id}/batches/",
            {"stage": "GL"},
        )
        self.assertEqual(gl_batches_response.status_code, status.HTTP_200_OK)
        gl_batches = gl_batches_response.data["data"]
        completed_gl_row = next(row for row in gl_batches if row["id"] == gl_batch.id)
        self.assertEqual(completed_gl_row["display_status"], "PR - Production")

        bl_batches_response = self.client.get(
            f"/api/production/orders/{self.order.id}/batches/",
            {"stage": "BL"},
        )
        self.assertEqual(bl_batches_response.status_code, status.HTTP_200_OK)
        bl_batches = bl_batches_response.data["data"]
        completed_bl_row = next(row for row in bl_batches if row["id"] == bl_batch.id)
        self.assertEqual(completed_bl_row["display_status"], "PR - Production")

        ad_batches_response = self.client.get(
            f"/api/production/orders/{self.order.id}/batches/",
            {"stage": "AD"},
        )
        self.assertEqual(ad_batches_response.status_code, status.HTTP_200_OK)
        ad_batches = ad_batches_response.data["data"]
        completed_ad_row = next(row for row in ad_batches if row["id"] == ad_batch_id)
        self.assertEqual(completed_ad_row["display_status"], "PR - Production")

    def test_pr_stage_records_only_include_pr_ready_orders_and_report_in_progress(self):
        create_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        ad_batch_id = create_response.data["data"]["id"]
        weight_entry_id = create_response.data["data"]["weight_entries"][0]["id"]

        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/start/",
            format="json",
        )
        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/weights/{weight_entry_id}/",
            {"entered_weight_grams": "250.000"},
            format="json",
        )
        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{ad_batch_id}/confirm/",
            format="json",
        )

        bl_batch = ProductionBatch.objects.get(production_order=self.order, stage=ProductionBatch.Stage.BL)
        self.client.post(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {
                "source_batch": bl_batch.id,
                "weight_kg": "180.500",
            },
            format="json",
        )
        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{bl_batch.id}/confirm/",
            format="json",
        )

        gl_batch = ProductionBatch.objects.get(production_order=self.order, stage=ProductionBatch.Stage.GL)
        self.client.post(
            f"/api/production/orders/{self.order.id}/output-captures/",
            {
                "source_batch": gl_batch.id,
                "weight_kg": "25.000",
            },
            format="json",
        )
        self.client.post(
            f"/api/production/orders/{self.order.id}/batches/{gl_batch.id}/confirm/",
            format="json",
        )

        unfinished_order = ProductionOrder.objects.create(
            production_id=f"PO-UNFINISHED-{self.unique_suffix.upper()}",
            production_type="WPE Additive Production",
            production_date=date.today(),
            status="PLANNED",
        )

        stage_response = self.client.get("/api/production/stage-records/?stage=PR")
        self.assertEqual(stage_response.status_code, status.HTTP_200_OK)

        stage_rows = stage_response.data["data"]["results"]
        matched_row = next(row for row in stage_rows if row["order_id"] == self.order.id)
        self.assertEqual(matched_row["workflow_status"], "PR")
        self.assertEqual(matched_row["status"], "IN_PROGRESS")
        self.assertNotIn(unfinished_order.id, [row["order_id"] for row in stage_rows])

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

    def test_ad_stage_records_list_only_additive_orders_and_batch_count(self):
        ProductionOrder.objects.create(
            production_id=f"PO-BL-{self.unique_suffix.upper()}",
            production_type="WPE Blend Production",
            production_date=date.today(),
        )

        create_response = self.client.post(
            f"/api/production/orders/{self.order.id}/batches/",
            {
                "stage": "AD",
                "bom_variant": self.bom.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        stage_response = self.client.get("/api/production/stage-records/?stage=AD")
        self.assertEqual(stage_response.status_code, status.HTTP_200_OK)

        stage_rows = stage_response.data["data"]["results"]
        self.assertEqual(len(stage_rows), 1)
        self.assertEqual(stage_rows[0]["order_id"], self.order.id)
        self.assertEqual(stage_rows[0]["production_type"], "WPE Additive Production")
        self.assertEqual(stage_rows[0]["batch_count"], 1)
        self.assertEqual(stage_rows[0]["workflow_status"], "AD")

    def test_ad_stage_records_without_batches_show_ad_status(self):
        stage_response = self.client.get("/api/production/stage-records/?stage=AD")
        self.assertEqual(stage_response.status_code, status.HTTP_200_OK)

        stage_rows = stage_response.data["data"]["results"]
        self.assertEqual(len(stage_rows), 1)
        self.assertEqual(stage_rows[0]["order_id"], self.order.id)
        self.assertEqual(stage_rows[0]["batch_count"], 0)
        self.assertEqual(stage_rows[0]["workflow_status"], "AD")

    def test_ad_stage_records_keep_legacy_orders_visible_after_bl_handoff(self):
        legacy_order = ProductionOrder.objects.create(
            production_id=f"PO-LEGACY-{self.unique_suffix.upper()}",
            production_type="WPE Blend Production",
            production_date=date.today(),
            status="IN_PROGRESS",
        )
        completed_ad_batch = ProductionBatch.objects.create(
            production_order=legacy_order,
            bom_variant=self.bom,
            stage=ProductionBatch.Stage.AD,
            status=ProductionBatch.BatchStatus.COMPLETED,
        )
        ProductionBatch.objects.filter(pk=completed_ad_batch.pk).update(completed_at=timezone.now())
        completed_ad_batch.refresh_from_db()
        ProductionBatch.objects.create(
            production_order=legacy_order,
            bom_variant=self.bom,
            stage=ProductionBatch.Stage.BL,
            status=ProductionBatch.BatchStatus.IN_PROGRESS,
            workflow_batch_no=completed_ad_batch.batch_no,
            started_at=timezone.now(),
        )

        stage_response = self.client.get("/api/production/stage-records/?stage=AD")
        self.assertEqual(stage_response.status_code, status.HTTP_200_OK)

        stage_rows = stage_response.data["data"]["results"]
        matched_row = next(row for row in stage_rows if row["order_id"] == legacy_order.id)
        self.assertEqual(matched_row["production_id"], legacy_order.production_id)
        self.assertEqual(matched_row["batch_count"], 1)
        self.assertEqual(matched_row["workflow_status"], "BL")

    def test_legacy_bl_batches_without_workflow_batch_no_use_ad_batch_number_for_display(self):
        legacy_order = ProductionOrder.objects.create(
            production_id=f"PO-LEGACY-BATCH-{self.unique_suffix.upper()}",
            production_type="WPE Additive Production",
            production_date=date.today(),
            status="IN_PROGRESS",
            batch_number="BATCH-LEGACY-AD",
        )
        completed_ad_batch = ProductionBatch.objects.create(
            production_order=legacy_order,
            bom_variant=self.bom,
            stage=ProductionBatch.Stage.AD,
            status=ProductionBatch.BatchStatus.COMPLETED,
            batch_no="BATCH-LEGACY-AD",
        )
        ProductionBatch.objects.filter(pk=completed_ad_batch.pk).update(workflow_batch_no=None)
        completed_ad_batch.refresh_from_db()
        pending_bl_batch = ProductionBatch.objects.create(
            production_order=legacy_order,
            bom_variant=self.bom,
            stage=ProductionBatch.Stage.BL,
            status=ProductionBatch.BatchStatus.PENDING,
            batch_no="BATCH-LEGACY-BL",
            notes="Moved from AD batch BATCH-LEGACY-AD.",
        )
        ProductionBatch.objects.filter(pk=pending_bl_batch.pk).update(workflow_batch_no=None)
        pending_bl_batch.refresh_from_db()

        batch_response = self.client.get(
            f"/api/production/orders/{legacy_order.id}/batches/",
            {"stage": "BL"},
        )
        self.assertEqual(batch_response.status_code, status.HTTP_200_OK)
        batch_rows = batch_response.data["data"]
        matched_bl_row = next(row for row in batch_rows if row["id"] == pending_bl_batch.id)
        self.assertEqual(matched_bl_row["batch_no"], pending_bl_batch.batch_no)
        self.assertEqual(matched_bl_row["display_batch_no"], completed_ad_batch.batch_no)

        stage_response = self.client.get("/api/production/stage-records/?stage=BL")
        self.assertEqual(stage_response.status_code, status.HTTP_200_OK)
        stage_rows = stage_response.data["data"]["results"]
        matched_stage_row = next(row for row in stage_rows if row["order_id"] == legacy_order.id)
        self.assertEqual(matched_stage_row["batch_no"], completed_ad_batch.batch_no)
        self.assertEqual(matched_stage_row["display_batch_no"], completed_ad_batch.batch_no)
        self.assertEqual(matched_stage_row["workflow_status"], "BL")


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
                "recipe_version": "",
                "batch_size": "5.000",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        recipe_id = response.data["id"]
        self.assertTrue(response.data["code"].startswith("REC"))
        self.assertEqual(response.data["recipe_version"], "v1")

        lookup_response = self.client.get("/api/production/recipes/lookup/")

        self.assertEqual(lookup_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(row["id"] == recipe_id for row in lookup_response.data))
