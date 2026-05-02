from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework.test import APITestCase

from .models import Item, ItemStockTransaction


class ItemImportTests(APITestCase):
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
                "item_code",
                "hsn_code",
                "unit",
                "quantity",
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

    def test_import_excel_generates_codes_and_updates_duplicate_stock(self):
        upload = self.build_excel_file(
            [
                [
                    "Profile Item",
                    "raw_material",
                    "polymer",
                    "ldpe",
                    "Virgin LDPE",
                    "MANUAL-1001",
                    "3901",
                    "kg",
                    10,
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
                    "MANUAL-1002",
                    "3901",
                    "kg",
                    2.5,
                    "Duplicate resin",
                    "Should update stock",
                    1,
                    1,
                ],
                [
                    "Profile Item",
                    "raw_material",
                    "polymer",
                    "ldpe",
                    "",
                    "",
                    "3901",
                    "kg",
                    1,
                    "Missing item name",
                    "",
                    0,
                    1,
                ],
            ]
        )

        response = self.client.post("/api/items/import/", {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, 207)
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(response.data["updated_count"], 1)
        self.assertEqual(response.data["failed_count"], 1)
        self.assertEqual(response.data["processed_count"], 3)
        self.assertEqual(response.data["stock_transactions_count"], 2)

        self.assertEqual(Item.objects.count(), 1)
        item = Item.objects.first()
        self.assertEqual(item.item_code, "PR000001")
        self.assertEqual(item.opening_stock, Decimal("10.000"))
        self.assertEqual(item.current_stock, Decimal("12.500"))
        self.assertEqual(ItemStockTransaction.objects.count(), 2)

    def test_create_duplicate_stock_movement_and_stock_analysis_api(self):
        payload = {
            "category": "Scrap Item",
            "group": "scrap",
            "sub_group": "end",
            "item_name": "End Scrap [WPE]",
            "unit": "kg",
            "opening_stock": "5.600",
        }

        create_response = self.client.post("/api/items", payload, format="json")

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["item_code"], "SI000001")
        self.assertEqual(create_response.data["current_stock"], "5.600")

        duplicate_response = self.client.post(
            "/api/items",
            {
                **payload,
                "quantity": "1.400",
                "ref_id": "DUP-1",
            },
            format="json",
        )

        self.assertEqual(duplicate_response.status_code, 200)
        self.assertFalse(duplicate_response.data["created"])
        self.assertEqual(Item.objects.count(), 1)

        item = Item.objects.get()

        inward_response = self.client.post(
            f"/api/items/{item.id}/stock/inward/",
            {"quantity": "3.000", "ref_id": "IN-1", "warehouse": "Recyclable Scrap"},
            format="json",
        )
        outward_response = self.client.post(
            f"/api/items/{item.id}/stock/outward/",
            {"quantity": "2.000", "ref_id": "OUT-1", "warehouse": "Recyclable Scrap"},
            format="json",
        )

        self.assertEqual(inward_response.status_code, 201)
        self.assertEqual(outward_response.status_code, 201)

        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("8.000"))

        analysis_response = self.client.get(f"/api/items/{item.id}/stock-analysis/")

        self.assertEqual(analysis_response.status_code, 200)
        self.assertEqual(
            analysis_response.data["columns"],
            [
                "S.NO.",
                "Date",
                "Ref ID",
                "Trans Type",
                "Sale Type",
                "Doc ID",
                "Contact",
                "Warehouse",
                "Bin",
                "Inwards",
                "Outwards",
                "Balance",
            ],
        )
        self.assertEqual(len(analysis_response.data["rows"]), 4)
        self.assertEqual(analysis_response.data["totals"]["Balance"], "8.000")
