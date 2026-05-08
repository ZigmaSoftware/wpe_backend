from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from openpyxl import Workbook
from rest_framework.test import APITestCase

from .models import Item, ItemStockTransaction


@override_settings(INTERNAL_API_KEY="test-internal-key")
class ItemMasterTests(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_KEY="test-internal-key")

    def build_excel_file(self, rows):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Items"
        sheet.append(
            [
                "product_type",
                "category",
                "group",
                "sub_group",
                "item_name",
                "external_item_id",
                "hsn_code",
                "unit",
                "product_details",
                "description",
                "min_max_status",
                "status",
            ]
        )

        for row in rows:
            sheet.append(row)

        buffer = BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        return SimpleUploadedFile(
            "items.xlsx",
            buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_create_item_returns_master_fields_only(self):
        response = self.client.post(
            "/api/items/",
            {
                "category": "Scrap Item",
                "group": "scrap",
                "sub_group": "end",
                "item_name": "End Scrap [WPE]",
                "unit": "kg",
                "opening_stock": "5.600",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertNotIn("opening_stock", response.data["data"])
        self.assertNotIn("current_stock", response.data["data"])
        self.assertNotIn("on_hand", response.data["data"])
        self.assertEqual(ItemStockTransaction.objects.count(), 0)

    def test_import_excel_upserts_item_master_only(self):
        upload = self.build_excel_file(
            [
                [
                    "Profile Item",
                    "raw_material",
                    "polymer",
                    "ldpe",
                    "Virgin LDPE",
                    "EXT-1001",
                    "3901",
                    "kg",
                    "Primary resin",
                    "Imported from Excel",
                    1,
                    1,
                ],
                [
                    "Profile Item",
                    "raw_material",
                    "polymer",
                    "ldpe",
                    "Virgin LDPE",
                    "EXT-1001",
                    "3901",
                    "kg",
                    "Updated resin note",
                    "Updated description",
                    1,
                    1,
                ],
            ]
        )

        response = self.client.post("/api/items/import/", {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["created_count"], 1)
        self.assertEqual(response.data["data"]["updated_count"], 1)
        self.assertEqual(Item.objects.count(), 1)
        self.assertEqual(ItemStockTransaction.objects.count(), 0)
        self.assertEqual(Item.objects.get().external_item_id, "EXT-1001")

    def test_stock_routes_are_removed_from_items_api(self):
        item = Item.objects.create(
            category="General Item",
            group="consumable",
            sub_group="packing",
            item_name="Tape Roll",
            unit="pcs",
        )

        response = self.client.post(
            f"/api/items/{item.id}/stock/inward/",
            {"quantity": "1.000"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
