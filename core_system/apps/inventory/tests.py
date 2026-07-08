from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.inventory.models import ProductionInventoryTransaction
from apps.items.models import Item
from apps.production.models import ProductionBatch, ProductionOrder, ProductionOutputCapture
from apps.store.models import StoreTransaction
from apps.store.services import apply_inward_stock, apply_outward_stock, get_warehouse_by_name


UserModel = get_user_model()


class WarehouseInventorySummaryApiTests(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(
            username="warehouse-inventory-user",
            email="warehouse-inventory@example.com",
            password="password123",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        self.url = "/api/inventory/warehouse-inventory/"

    def test_requires_warehouse_name_and_returns_summary_for_selected_warehouse(self):
        warehouse = get_warehouse_by_name("QC Pending Warehouse - CBE")
        primary_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="hdpe",
            item_name="Warehouse Summary Primary",
            unit="kg",
        )
        secondary_item = Item.objects.create(
            category="Consumable",
            group="packing",
            sub_group="labels",
            item_name="Warehouse Summary Secondary",
            unit="pcs",
        )
        apply_inward_stock(
            item=primary_item,
            warehouse=warehouse,
            quantity="12.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="WH-QC-OPEN-1",
            created_by=self.user,
            transaction_date="2026-06-01",
        )
        apply_outward_stock(
            item=primary_item,
            warehouse=warehouse,
            quantity="2.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_OUTWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="WH-QC-OUT-1",
            created_by=self.user,
            transaction_date="2026-06-02",
        )
        apply_inward_stock(
            item=secondary_item,
            warehouse=warehouse,
            quantity="5.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="WH-QC-IN-2",
            created_by=self.user,
            transaction_date="2026-06-03",
        )

        response = self.client.get(
            self.url,
            {
                "warehouse_name": "QC Pending Warehouse - CBE",
                "item_id": primary_item.id,
                "search": "Primary",
                "page": 1,
                "page_size": 10,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 1)
        row = response.data["data"]["results"][0]
        self.assertEqual(row["item_id"], primary_item.id)
        self.assertEqual(row["item_name"], primary_item.item_name)
        self.assertEqual(row["current_stock"], "10.000")
        self.assertEqual(row["total_inward"], "12.000")
        self.assertEqual(row["total_outward"], "2.000")
        self.assertTrue(row["last_updated"])

    def test_missing_warehouse_name_is_rejected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("warehouse_name", response.data)


class ProductionInventoryApiTests(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(
            username="production-inventory-user",
            email="production-inventory@example.com",
            password="password123",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        self.url = "/api/inventory/production-inventory/"

    def _create_stage_row(
        self,
        *,
        production_id: str,
        planned_weight: str,
        batch_no: str,
        recipe_no: str,
        stage: str = ProductionInventoryTransaction.Stage.BLEND_STORE,
        captured_qty: str,
        outward_qty: str,
        created_at,
        scancode: str,
        lot_code: str,
    ):
        order, _created = ProductionOrder.objects.get_or_create(
            production_id=production_id,
            defaults={
                "production_type": "BLENDING_PRODUCTION",
                "production_date": created_at.date(),
                "planned_weight": planned_weight,
            },
        )
        batch = ProductionBatch.objects.create(
            production_order=order,
            stage=ProductionBatch.Stage.BL,
            batch_no=batch_no,
            workflow_batch_no=batch_no,
            status=ProductionBatch.BatchStatus.COMPLETED,
        )
        capture = ProductionOutputCapture.objects.create(
            production_order=order,
            source_batch=batch,
            sequence=order.output_captures.count() + 1,
            scancode_id=scancode,
            recipe_no=recipe_no,
            quantity_kg=captured_qty,
            weight_kg=captured_qty,
            binlot=lot_code,
            captured_at=created_at,
        )
        row = ProductionInventoryTransaction.objects.create(
            stage=stage,
            movement_key=f"{stage}-{production_id}-{batch_no}",
            batch_code=batch_no,
            production_order=order,
            production_id=production_id,
            production_type="BLENDING_PRODUCTION",
            source_batch=batch,
            output_capture=capture,
            item_code=f"ITEM-{production_id}",
            item_name=f"Item {production_id}",
            inward_qty=captured_qty,
            outward_qty=outward_qty,
            balance_qty="0.000",
            uom="kgs",
            status=ProductionInventoryTransaction.Status.IN_PROGRESS,
            created_by=self.user,
        )
        ProductionInventoryTransaction.objects.filter(pk=row.pk).update(
            balance_qty=models.F("inward_qty") - models.F("outward_qty"),
        )
        ProductionInventoryTransaction.objects.filter(pk=row.pk).update(created_at=created_at, updated_at=created_at)
        row.refresh_from_db()
        return row

    def test_group_by_production_id_returns_store_summary_rows_with_totals(self):
        now = timezone.now()
        self._create_stage_row(
            production_id="BL-1001",
            planned_weight="250.000",
            batch_no="BATCH-BL-1001-01",
            recipe_no="RCP-1001",
            captured_qty="100.000",
            outward_qty="40.000",
            created_at=now - timedelta(hours=2),
            scancode="SCAN-1001-01",
            lot_code="BIN-1001-01",
        )
        self._create_stage_row(
            production_id="BL-1001",
            planned_weight="250.000",
            batch_no="BATCH-BL-1001-02",
            recipe_no="RCP-1001",
            captured_qty="80.000",
            outward_qty="0.000",
            created_at=now - timedelta(hours=1),
            scancode="SCAN-1001-02",
            lot_code="BIN-1001-02",
        )
        self._create_stage_row(
            production_id="BL-1002",
            planned_weight="150.000",
            batch_no="BATCH-BL-1002-01",
            recipe_no="RCP-1002",
            captured_qty="50.000",
            outward_qty="20.000",
            created_at=now - timedelta(minutes=30),
            scancode="SCAN-1002-01",
            lot_code="BIN-1002-01",
        )

        response = self.client.get(
            self.url,
            {
                "stage": ProductionInventoryTransaction.Stage.BLEND_STORE,
                "include_history": "true",
                "group_by": "production_id",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data["data"]
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["totals"]["total_inward_weight"], "230.000")
        self.assertEqual(payload["totals"]["total_outward_weight"], "60.000")
        self.assertEqual(payload["totals"]["total_current_weight"], "170.000")
        self.assertEqual(payload["totals"]["planned_weight"], "400.000")

        grouped_row = next(row for row in payload["results"] if row["production_id"] == "BL-1001")
        self.assertEqual(grouped_row["batch_count"], 2)
        self.assertEqual(grouped_row["recipe"], "RCP-1001")
        self.assertEqual(grouped_row["production_type"], "BLENDING_PRODUCTION")
        self.assertEqual(grouped_row["total_weight"], "180.000")
        self.assertEqual(grouped_row["planned_weight"], "250.000")
        self.assertEqual(grouped_row["created_by"], self.user.username)
        self.assertTrue(grouped_row["created_at"])

    def test_production_id_filter_returns_only_matching_stage_rows(self):
        now = timezone.now()
        first_row = self._create_stage_row(
            production_id="BL-2001",
            planned_weight="120.000",
            batch_no="BATCH-BL-2001-01",
            recipe_no="RCP-2001",
            captured_qty="60.000",
            outward_qty="10.000",
            created_at=now - timedelta(minutes=20),
            scancode="SCAN-2001-01",
            lot_code="BIN-2001-01",
        )
        self._create_stage_row(
            production_id="BL-2002",
            planned_weight="140.000",
            batch_no="BATCH-BL-2002-01",
            recipe_no="RCP-2002",
            captured_qty="70.000",
            outward_qty="0.000",
            created_at=now - timedelta(minutes=10),
            scancode="SCAN-2002-01",
            lot_code="BIN-2002-01",
        )

        response = self.client.get(
            self.url,
            {
                "stage": ProductionInventoryTransaction.Stage.BLEND_STORE,
                "include_history": "true",
                "production_id": "BL-2001",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data["data"]
        self.assertEqual(payload["count"], 1)
        row = payload["results"][0]
        self.assertEqual(row["id"], first_row.id)
        self.assertEqual(row["production_id"], "BL-2001")
        self.assertEqual(row["batch_no"], "BATCH-BL-2001-01")
        self.assertEqual(row["captured_weight"], "60.000")
        self.assertEqual(row["scancode"], "SCAN-2001-01")
        self.assertEqual(row["binlot"], "BIN-2001-01")
