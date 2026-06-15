from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.admin_master.models import Staff, UserCreation, UserType
from apps.items.models import Item

from .models import StockRequest, StoreStock, StoreTransaction
from .services import add_stock_from_grn, apply_inward_stock, apply_outward_stock, get_blending_warehouse, get_store_warehouse


@override_settings(INTERNAL_API_KEY="test-internal-key")
class StoreWorkflowTests(APITestCase):
    def create_role_user(self, *, username: str, role_name: str):
        user = get_user_model().objects.create_user(username=username, password="test-pass-123")
        staff = Staff.objects.create(name=f"{username} Staff")
        user_type, _ = UserType.objects.get_or_create(name=role_name)
        UserCreation.objects.create(user=user, staff=staff, user_type=user_type)
        return user

    def make_auth_client(self, user):
        access_token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        return client

    def setUp(self):
        self.store_user = self.create_role_user(username="store-user", role_name="Store User")
        self.blending_user = self.create_role_user(username="blending-user", role_name="Blending User")
        self.blending_head = self.create_role_user(username="blending-head", role_name="Blending Head")
        self.store_client = self.make_auth_client(self.store_user)
        self.blending_client = self.make_auth_client(self.blending_user)
        self.blending_head_client = self.make_auth_client(self.blending_head)
        self.store_warehouse = get_store_warehouse()
        self.blending_warehouse = get_blending_warehouse()

    def approve_by_blending_head(self, request_id: int):
        return self.blending_head_client.post(
            f"/api/blending/head-approvals/{request_id}/approve/",
            {"remarks": "Approved by Blending Head"},
            format="json",
        )

    def test_approve_request_transfers_stock_between_warehouses(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="ldpe",
            item_name="Virgin LDPE",
            unit="kg",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.store_warehouse,
            quantity="100.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="OPEN-1",
            created_by=self.store_user,
        )

        request_response = self.blending_client.post(
            "/api/blending/store-requests/",
            {
                "remarks": "Material needed for batch 24-A",
                "items": [{"item_id": item.id, "quantity": "50.000"}],
            },
            format="json",
        )
        request_id = request_response.data["data"]["id"]
        self.assertEqual(self.approve_by_blending_head(request_id).status_code, 200)

        approve_response = self.store_client.post(
            f"/api/store/requests/{request_id}/approve/",
            {"approval_remarks": "Approved for production"},
            format="json",
        )

        self.assertEqual(approve_response.status_code, 200)
        source_stock = StoreStock.objects.get(item=item, warehouse=self.store_warehouse)
        destination_stock = StoreStock.objects.get(item=item, warehouse=self.blending_warehouse)
        request_item = StockRequest.objects.prefetch_related("items").get(pk=request_id).items.get(item=item)

        self.assertEqual(source_stock.available_qty, Decimal("50.000"))
        self.assertEqual(destination_stock.available_qty, Decimal("50.000"))
        self.assertEqual(request_item.approved_qty, Decimal("50.000"))
        self.assertEqual(request_item.issued_qty, Decimal("50.000"))

    def test_partial_approval_allows_per_item_quantities(self):
        first_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="ldpe",
            item_name="LDPE Granules",
            unit="kg",
        )
        second_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="hdpe",
            item_name="HDPE Granules",
            unit="kg",
        )
        apply_inward_stock(
            item=first_item,
            warehouse=self.store_warehouse,
            quantity="20.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="OPEN-3",
            created_by=self.store_user,
        )
        apply_inward_stock(
            item=second_item,
            warehouse=self.store_warehouse,
            quantity="20.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="OPEN-4",
            created_by=self.store_user,
        )

        request_response = self.blending_client.post(
            "/api/blending/store-requests/",
            {
                "remarks": "Partial approval check",
                "items": [
                    {"item_id": first_item.id, "quantity": "10.000"},
                    {"item_id": second_item.id, "quantity": "6.000"},
                ],
            },
            format="json",
        )
        request_id = request_response.data["data"]["id"]
        self.assertEqual(self.approve_by_blending_head(request_id).status_code, 200)

        approve_response = self.store_client.post(
            f"/api/store/requests/{request_id}/approve/",
            {
                "items": [
                    {"item": first_item.id, "provided_qty": "4.000", "remarks": "Only partial stock released"},
                    {"item": second_item.id, "provided_qty": "0.000", "remarks": "No stock released"},
                ],
            },
            format="json",
        )

        self.assertEqual(approve_response.status_code, 200)
        stock_request = StockRequest.objects.prefetch_related("items").get(pk=request_id)
        first_request_item = stock_request.items.get(item=first_item)
        second_request_item = stock_request.items.get(item=second_item)

        self.assertEqual(stock_request.status, StockRequest.Status.PARTIALLY_APPROVED)
        self.assertEqual(first_request_item.approved_qty, Decimal("4.000"))
        self.assertEqual(first_request_item.issued_qty, Decimal("4.000"))
        self.assertEqual(first_request_item.remarks, "Only partial stock released")
        self.assertEqual(second_request_item.approved_qty, Decimal("0.000"))
        self.assertEqual(second_request_item.issued_qty, Decimal("0.000"))
        self.assertEqual(approve_response.data["data"]["issue_transactions"][0]["quantity"], "4.000")
        self.assertEqual(approve_response.data["data"]["receipt_transactions"][0]["quantity"], "4.000")

    def test_legacy_request_stock_endpoint_sets_additive_metadata(self):
        item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Processing Additive A",
            unit="kg",
        )

        response = self.blending_client.post(
            "/api/store/request-stock/",
            {
                "item_id": item.id,
                "quantity": "5.000",
                "request_type": "ADDITIVE",
                "department": "BLENDING",
                "request_date": "2026-05-24",
                "require_date": "2026-05-25",
                "require_time": "10:45:00",
                "requested_for_name": "Shift Lead",
                "request_reason": "Batch replenishment",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        stock_request = StockRequest.objects.prefetch_related("items").get(pk=response.data["request"]["id"])
        self.assertEqual(stock_request.request_type, StockRequest.RequestType.ADDITIVE)
        self.assertEqual(stock_request.department, "BLENDING")
        self.assertEqual(str(stock_request.request_date), "2026-05-24")
        self.assertEqual(str(stock_request.require_date), "2026-05-25")
        self.assertEqual(str(stock_request.require_time), "10:45:00")
        self.assertEqual(stock_request.requested_for_name, "Shift Lead")
        self.assertEqual(stock_request.request_reason, "Batch replenishment")
        self.assertEqual(stock_request.items.first().requested_qty, Decimal("5.000"))

    def test_store_requests_list_exposes_flat_compatibility_fields(self):
        item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Mixer Additive",
            unit="kg",
        )
        request_response = self.blending_client.post(
            "/api/store/request-stock/",
            {
                "item_id": item.id,
                "quantity": "2.500",
                "request_type": "ADDITIVE",
                "department": "BLENDING",
                "request_date": "2026-05-26",
                "require_date": "2026-05-27",
                "require_time": "09:30:00",
                "requested_for_name": "Mixer Operator",
                "request_reason": "Line refill",
            },
            format="json",
        )
        self.assertEqual(self.approve_by_blending_head(request_response.data["request"]["id"]).status_code, 200)

        response = self.store_client.get("/api/store/requests/")

        self.assertEqual(response.status_code, 200)
        row = response.data["data"]["results"][0]
        self.assertEqual(row["item"], item.id)
        self.assertEqual(row["quantity"], "2.500")
        self.assertEqual(row["request_type"], "ADDITIVE")
        self.assertEqual(row["request_date"], "2026-05-26")
        self.assertEqual(row["require_date"], "2026-05-27")
        self.assertEqual(row["require_time"], "09:30:00")
        self.assertEqual(row["requested_for_name"], "Mixer Operator")

    def test_store_cannot_approve_request_pending_blending_head_approval(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="lldpe",
            item_name="Pending Head Resin",
            unit="kg",
        )
        request_response = self.blending_client.post(
            "/api/blending/store-requests/",
            {"items": [{"item_id": item.id, "quantity": "2.000"}]},
            format="json",
        )

        approve_response = self.store_client.post(
            f"/api/store/requests/{request_response.data['data']['id']}/approve/",
            {"approval_remarks": "Should be blocked"},
            format="json",
        )

        self.assertEqual(approve_response.status_code, 400)
        self.assertEqual(approve_response.data["status"], "This request is pending Blending Head approval.")

    def test_store_stock_list_is_readable_by_blending_user(self):
        item = Item.objects.create(
            category="General Item",
            group="consumable",
            sub_group="packing",
            item_name="Tape Roll",
            unit="pcs",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.store_warehouse,
            quantity="5.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="OPEN-2",
            created_by=self.store_user,
        )

        response = self.blending_client.get("/api/store/stock/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["results"][0]["quantity"], "5.000")

    def test_add_stock_from_grn_is_idempotent(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="eva",
            item_name="EVA Resin",
            unit="kg",
        )
        payload = {
            "unique_id": "WPE-00000001",
            "process_status": "Moved to GRN",
            "document_details": {
                "grn_no": "GRN-1001",
                "grn_date": "2026-05-05",
            },
            "supplier_details": {
                "trade_name": "Acme Polymers",
            },
            "items": [
                {
                    "item_id": str(item.id),
                    "product_description": item.item_name,
                    "unit": "kg",
                    "accepted_qty": "12.500",
                }
            ],
        }

        first_result = add_stock_from_grn(payload, created_by=self.store_user)
        second_result = add_stock_from_grn(payload, created_by=self.store_user)

        stock_row = StoreStock.objects.get(item=item, warehouse=self.store_warehouse)

        self.assertEqual(first_result["processed_references"], ["WPE-00000001:1"])
        self.assertEqual(second_result["processed_references"], [])
        self.assertEqual(second_result["skipped_references"], ["WPE-00000001:1"])
        self.assertEqual(stock_row.available_qty, Decimal("12.500"))

    def test_store_stock_list_exposes_grn_purchase_group_metadata(self):
        first_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="hdpe",
            item_name="Grouped Resin A",
            unit="kg",
        )
        second_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="hdpe",
            item_name="Grouped Resin B",
            unit="kg",
        )
        payload = {
            "unique_id": "WPE-00000003",
            "process_status": "Moved to GRN",
            "document_details": {
                "grn_no": "GRN-1003",
                "grn_date": "2026-05-05",
            },
            "supplier_details": {
                "trade_name": "Grouped Supplier",
            },
            "items": [
                {
                    "item_id": str(first_item.id),
                    "product_description": first_item.item_name,
                    "unit": "kg",
                    "accepted_qty": "10.000",
                },
                {
                    "item_id": str(second_item.id),
                    "product_description": second_item.item_name,
                    "unit": "kg",
                    "accepted_qty": "20.000",
                },
            ],
        }

        add_stock_from_grn(payload, created_by=self.store_user)
        response = self.blending_client.get("/api/blending/request-stock/")

        rows = response.data["data"]["results"]
        grouped_rows = [row for row in rows if row["item"] in {first_item.id, second_item.id}]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(grouped_rows), 2)
        self.assertEqual({row["source_group_key"] for row in grouped_rows}, {"GRN:GRN-1003"})
        self.assertEqual({row["source_reference"] for row in grouped_rows}, {"GRN-1003"})
        self.assertEqual({row["source_supplier"] for row in grouped_rows}, {"Grouped Supplier"})

    def test_add_stock_from_grn_requires_moved_to_grn_status(self):
        payload = {
            "unique_id": "WPE-00000002",
            "process_status": "Moved to QCR",
            "document_details": {
                "grn_no": "GRN-1002",
                "grn_date": "2026-05-05",
            },
            "items": [
                {
                    "item_id": "ITEM-UNREADY-1",
                    "product_description": "Unready Resin",
                    "unit": "kg",
                    "accepted_qty": "1.000",
                }
            ],
        }

        with self.assertRaises(ValidationError) as exc:
            add_stock_from_grn(payload, created_by=self.store_user)

        self.assertIn("process_status", exc.exception.detail)

    def test_store_inventory_summary_api_returns_current_stock_totals(self):
        primary_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="hdpe",
            item_name="Primary Store Item",
            unit="kg",
        )
        secondary_item = Item.objects.create(
            category="Consumable",
            group="packing",
            sub_group="labels",
            item_name="Secondary Store Item",
            unit="pcs",
        )
        apply_inward_stock(
            item=primary_item,
            warehouse=self.store_warehouse,
            quantity="10.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="STORE-OPEN-1",
            created_by=self.store_user,
            transaction_date="2026-05-10",
        )
        apply_outward_stock(
            item=primary_item,
            warehouse=self.store_warehouse,
            quantity="4.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_OUTWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-OUT-1",
            created_by=self.store_user,
            transaction_date="2026-05-11",
        )
        apply_inward_stock(
            item=secondary_item,
            warehouse=self.store_warehouse,
            quantity="2.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-IN-2",
            created_by=self.store_user,
            transaction_date="2026-05-01",
        )

        summary_response = self.store_client.get(
            f"/api/store/inventory/summary/?item_id={primary_item.id}&search=Primary&page=1&page_size=10"
        )

        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.data["data"]["count"], 1)
        self.assertEqual(summary_response.data["data"]["results"][0]["item_id"], primary_item.id)
        self.assertEqual(summary_response.data["data"]["results"][0]["item_name"], primary_item.item_name)
        self.assertEqual(summary_response.data["data"]["results"][0]["total_inward"], "10.000")
        self.assertEqual(summary_response.data["data"]["results"][0]["total_outward"], "4.000")
        self.assertEqual(summary_response.data["data"]["results"][0]["current_stock"], "6.000")
        self.assertTrue(summary_response.data["data"]["results"][0]["last_updated"])

    def test_store_inventory_history_api_returns_latest_first(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="lldpe",
            item_name="History Store Item",
            unit="kg",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.store_warehouse,
            quantity="10.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="STORE-HIST-OPEN",
            created_by=self.store_user,
            transaction_date="2026-05-10",
        )
        apply_outward_stock(
            item=item,
            warehouse=self.store_warehouse,
            quantity="3.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_OUTWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-HIST-OUT",
            created_by=self.store_user,
            transaction_date="2026-05-11",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.store_warehouse,
            quantity="2.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-HIST-IN",
            created_by=self.store_user,
            transaction_date="2026-05-12",
        )

        response = self.store_client.get(f"/api/store/inventory/{item.id}/history/?page=1&page_size=10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 3)
        latest_row = response.data["data"]["results"][0]
        self.assertEqual(latest_row["transaction_type"], "INWARD")
        self.assertEqual(latest_row["quantity"], "2.000")
        self.assertEqual(latest_row["opening_stock"], "7.000")
        self.assertEqual(latest_row["closing_stock"], "9.000")
        self.assertEqual(latest_row["reference_no"], "STORE-HIST-IN")
        self.assertEqual(latest_row["module"], "MANUAL")
        self.assertEqual(latest_row["created_by"], self.store_user.username)

    def test_store_inventory_legacy_monitoring_endpoints_are_removed(self):
        response = self.store_client.get("/api/store/stock/current/")
        self.assertEqual(response.status_code, 404)

        response = self.store_client.post("/api/store/stock/inward/", {}, format="json")
        self.assertEqual(response.status_code, 404)

        response = self.store_client.post("/api/store/stock/outward/", {}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_store_inventory_outward_rejects_quantity_above_current_stock(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="pp",
            item_name="Constrained Store Item",
            unit="kg",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.store_warehouse,
            quantity="3.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-IN-3",
            created_by=self.store_user,
            transaction_date="2026-05-10",
        )

        with self.assertRaises(ValidationError) as exc:
            apply_outward_stock(
                item=item,
                warehouse=self.store_warehouse,
                quantity="5.000",
                transaction_type=StoreTransaction.TransactionType.MANUAL_OUTWARD,
                reference_type=StoreTransaction.ReferenceType.MANUAL,
                reference_id="STORE-OUT-2",
                created_by=self.store_user,
                transaction_date="2026-05-11",
            )

        self.assertIn("quantity", exc.exception.detail)
        self.assertEqual(StoreTransaction.objects.filter(item=item, warehouse=self.store_warehouse).count(), 1)
