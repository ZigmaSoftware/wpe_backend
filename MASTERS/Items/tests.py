from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework.test import APITestCase

from .models import Item


class ItemImportTests(APITestCase):
    def build_excel_file(self, rows):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Items"
        sheet.append(
            [
                "category",
                "group",
                "sub_group",
                "item_name",
                "item_code",
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

    def test_import_excel_creates_valid_rows_and_reports_invalid_rows(self):
        upload = self.build_excel_file(
            [
                [
                    "raw_material",
                    "polymer",
                    "ldpe",
                    "Virgin LDPE",
                    "ITM-1001",
                    "3901",
                    "kg",
                    "Primary resin",
                    "Imported from Excel",
                    1,
                    1,
                ],
                [
                    "raw_material",
                    "polymer",
                    "ldpe",
                    "Missing Code",
                    "",
                    "3901",
                    "kg",
                    "Missing item code",
                    "",
                    0,
                    1,
                ],
            ]
        )

        response = self.client.post("/api/items/import/", {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, 207)
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(response.data["failed_count"], 1)
        self.assertEqual(response.data["processed_count"], 2)
        self.assertEqual(Item.objects.count(), 1)
        self.assertEqual(Item.objects.first().item_code, "ITM-1001")
