from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.admin_master.models import Staff, UserCreation, UserType
from apps.items.models import Item
from apps.store.models import StockRequest, StoreTransaction
from apps.store.services import apply_inward_stock, apply_outward_stock, get_blending_warehouse, get_store_warehouse
from apps.wpe_masters.models import DepartmentMaster


@override_settings(INTERNAL_API_KEY="test-internal-key")
class BlendingStoreRequestTests(APITestCase):
    def create_role_user(self, *, username: str, role_name: str, department_name: str | None = None):
        user = get_user_model().objects.create_user(username=username, password="test-pass-123")
        staff = Staff.objects.create(name=f"{username} Staff")
        department = None
        if department_name:
            department = DepartmentMaster.objects.create(name=department_name)
        user_type, _ = UserType.objects.get_or_create(name=role_name, defaults={"department": department})
        UserCreation.objects.create(user=user, staff=staff, user_type=user_type)
        return user

    def make_auth_client(self, user):
        access_token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        return client

    def setUp(self):
        self.blending_user = self.create_role_user(
            username="blending-user",
            role_name="Blending User",
            department_name="Compounding",
        )
        self.store_user = self.create_role_user(username="store-user", role_name="Store User")
        self.blending_head = self.create_role_user(username="blending-head", role_name="Blending Head")
        self.client = self.make_auth_client(self.blending_user)
        self.store_user_client = self.make_auth_client(self.store_user)
        self.blending_head_client = self.make_auth_client(self.blending_head)
        self.blending_warehouse = get_blending_warehouse()
        self.store_warehouse = get_store_warehouse()

    def test_request_stock_creates_pending_store_request_with_items(self):
        item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Processing Additive A",
            unit="kg",
        )

        response = self.client.post(
            "/api/blending/store-requests/",
            {
                "remarks": "Need material for mixing line 1",
                "request_type": "ADDITIVE",
                "department": "BLENDING",
                "request_date": "2026-05-20",
                "require_date": "2026-05-21",
                "require_time": "14:30:00",
                "requested_for_name": "Blending Supervisor",
                "request_reason": "Required for additive batch run",
                "items": [{"item_id": item.id, "quantity": "50.000"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["status"], StockRequest.Status.PENDING_HEAD_APPROVAL)
        self.assertEqual(response.data["data"]["request_type"], StockRequest.RequestType.ADDITIVE)
        self.assertEqual(response.data["data"]["item"], item.id)
        self.assertEqual(response.data["data"]["department"], "Compounding")
        self.assertEqual(str(response.data["data"]["request_date"]), "2026-05-20")
        self.assertEqual(str(response.data["data"]["require_date"]), "2026-05-21")
        self.assertEqual(str(response.data["data"]["require_time"]), "14:30:00")

    def test_head_approval_moves_request_to_store_queue_without_inventory_movement(self):
        item = Item.objects.create(
            category="Raw Material",
            group="blend",
            sub_group="approval",
            item_name="Head Approval Material",
            unit="kg",
        )
        create_response = self.client.post(
            "/api/blending/store-requests/",
            {
                "department": "BLENDING",
                "items": [{"item_id": item.id, "quantity": "8.000"}],
            },
            format="json",
        )
        request_id = create_response.data["data"]["id"]
        stock_request = StockRequest.objects.get(pk=request_id)
        stock_request.department = "BLENDING"
        stock_request.save(update_fields=["department"])
        transaction_count = StoreTransaction.objects.count()

        head_queue = self.blending_head_client.get("/api/blending/head-approvals/")
        before_store_queue = self.store_user_client.get("/api/store/requests/")
        approval_response = self.blending_head_client.post(
            f"/api/blending/head-approvals/{request_id}/approve/",
            {"remarks": "Approved for batch BL-104"},
            format="json",
        )
        after_store_queue = self.store_user_client.get("/api/store/requests/")

        self.assertEqual(head_queue.data["data"]["count"], 1)
        self.assertEqual(before_store_queue.data["data"]["count"], 0)
        self.assertEqual(approval_response.status_code, 200)
        self.assertEqual(approval_response.data["data"]["status"], StockRequest.Status.PENDING_STORE_ISSUE)
        self.assertEqual(approval_response.data["data"]["head_action_by"], self.blending_head.id)
        self.assertEqual(approval_response.data["data"]["head_approval_remarks"], "Approved for batch BL-104")
        self.assertIsNotNone(approval_response.data["data"]["head_action_at"])
        self.assertEqual(after_store_queue.data["data"]["count"], 1)
        self.assertEqual(StoreTransaction.objects.count(), transaction_count)

    def test_head_approval_limits_store_queue_to_head_accepted_quantities(self):
        first_item = Item.objects.create(
            category="Raw Material",
            group="blend",
            sub_group="approval",
            item_name="Head Accepted Material",
            unit="kg",
        )
        second_item = Item.objects.create(
            category="Raw Material",
            group="blend",
            sub_group="approval",
            item_name="Head Rejected Material",
            unit="kg",
        )
        create_response = self.client.post(
            "/api/blending/store-requests/",
            {
                "items": [
                    {"item_id": first_item.id, "quantity": "10.000"},
                    {"item_id": second_item.id, "quantity": "5.000"},
                ],
            },
            format="json",
        )
        request_id = create_response.data["data"]["id"]

        approval_response = self.blending_head_client.post(
            f"/api/blending/head-approvals/{request_id}/approve/",
            {
                "remarks": "Head reviewed line quantities",
                "items": [
                    {"item": first_item.id, "accepted_qty": "4.000", "remarks": "Only four needed"},
                    {"item": second_item.id, "accepted_qty": "0.000", "remarks": "Not required"},
                ],
            },
            format="json",
        )
        store_queue_response = self.store_user_client.get("/api/store/requests/")

        self.assertEqual(approval_response.status_code, 200)
        self.assertEqual(approval_response.data["data"]["status"], StockRequest.Status.PENDING_STORE_ISSUE)
        self.assertEqual(len(approval_response.data["data"]["items"]), 1)
        self.assertEqual(approval_response.data["data"]["items"][0]["item"], first_item.id)
        self.assertEqual(Decimal(approval_response.data["data"]["items"][0]["requested_qty"]), Decimal("4.000"))
        self.assertEqual(store_queue_response.data["data"]["count"], 1)
        self.assertEqual(len(store_queue_response.data["data"]["results"][0]["items"]), 1)
        self.assertEqual(Decimal(store_queue_response.data["data"]["results"][0]["items"][0]["requested_qty"]), Decimal("4.000"))

    def test_head_rejection_does_not_change_inventory(self):
        item = Item.objects.create(
            category="Raw Material",
            group="blend",
            sub_group="approval",
            item_name="Rejected Head Material",
            unit="kg",
        )
        create_response = self.client.post(
            "/api/blending/store-requests/",
            {"items": [{"item_id": item.id, "quantity": "3.000"}]},
            format="json",
        )
        request_id = create_response.data["data"]["id"]
        transaction_count = StoreTransaction.objects.count()

        rejection_response = self.blending_head_client.post(
            f"/api/blending/head-approvals/{request_id}/reject/",
            {"remarks": "Existing stock is sufficient"},
            format="json",
        )

        self.assertEqual(rejection_response.status_code, 200)
        self.assertEqual(rejection_response.data["data"]["status"], StockRequest.Status.HEAD_REJECTED)
        self.assertEqual(StoreTransaction.objects.count(), transaction_count)

    def test_regular_blending_user_cannot_review_head_approval(self):
        item = Item.objects.create(
            category="Raw Material",
            group="blend",
            sub_group="approval",
            item_name="Protected Head Approval Material",
            unit="kg",
        )
        create_response = self.client.post(
            "/api/blending/store-requests/",
            {"items": [{"item_id": item.id, "quantity": "3.000"}]},
            format="json",
        )

        approval_response = self.client.post(
            f"/api/blending/head-approvals/{create_response.data['data']['id']}/approve/",
            {"remarks": "Should not be allowed"},
            format="json",
        )

        self.assertEqual(approval_response.status_code, 403)

    def test_legacy_additive_request_endpoint_still_works(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="lldpe",
            item_name="Legacy Requestable Resin",
            unit="kg",
        )

        response = self.client.post(
            "/api/blending/request-stock/",
            {
                "item_id": item.id,
                "quantity": "10.000",
                "requested_for_name": "Shift Lead",
                "request_reason": "Line refill",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["request"]["request_type"], "ADDITIVE")
        self.assertEqual(response.data["request"]["department"], "Compounding")

    def test_request_stock_get_returns_requestable_store_stock_for_dropdown(self):
        additive_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Dropdown Additive",
            unit="kg",
        )
        non_additive_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="lldpe",
            item_name="Dropdown Resin",
            unit="kg",
        )
        apply_inward_stock(
            item=additive_item,
            warehouse=self.store_warehouse,
            quantity="12.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-DD-1",
            created_by=self.store_user,
        )
        apply_inward_stock(
            item=non_additive_item,
            warehouse=self.store_warehouse,
            quantity="7.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-DD-2",
            created_by=self.store_user,
        )

        response = self.client.get("/api/blending/request-stock/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 2)
        self.assertEqual(
            {row["item"] for row in response.data["data"]["results"]},
            {additive_item.id, non_additive_item.id},
        )
        self.assertEqual(
            {row["warehouse_code"] for row in response.data["data"]["results"]},
            {self.store_warehouse.code},
        )

    def test_request_stock_get_supports_search_against_store_dropdown_data(self):
        matching_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Searchable Additive Alpha",
            unit="kg",
        )
        non_matching_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Other Additive Beta",
            unit="kg",
        )
        apply_inward_stock(
            item=matching_item,
            warehouse=self.store_warehouse,
            quantity="12.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-SRCH-1",
            created_by=self.store_user,
        )
        apply_inward_stock(
            item=non_matching_item,
            warehouse=self.store_warehouse,
            quantity="9.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-SRCH-2",
            created_by=self.store_user,
        )

        response = self.client.get("/api/blending/request-stock/?search=Alpha")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(response.data["data"]["results"][0]["item"], matching_item.id)

    def test_cancel_pending_request(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="eva",
            item_name="EVA Resin",
            unit="kg",
        )
        create_response = self.client.post(
            "/api/blending/store-requests/",
            {"items": [{"item_id": item.id, "quantity": "5.000"}]},
            format="json",
        )
        request_id = create_response.data["data"]["id"]

        cancel_response = self.client.post(
            f"/api/blending/store-requests/{request_id}/cancel/",
            {"remarks": "Requirement changed"},
            format="json",
        )

        self.assertEqual(cancel_response.status_code, 200)
        self.assertEqual(cancel_response.data["data"]["status"], StockRequest.Status.CANCELLED)

    def test_pending_store_request_can_be_updated_and_returns_all_item_details(self):
        item_one = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Base Additive",
            unit="kg",
        )
        item_two = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Second Additive",
            unit="kg",
        )

        create_response = self.client.post(
            "/api/blending/store-requests/",
            {
                "request_type": "ADDITIVE",
                "requested_for_name": "Initial User",
                "request_reason": "Initial request",
                "items": [{"item_id": item_one.id, "quantity": "5.000"}],
            },
            format="json",
        )
        request_id = create_response.data["data"]["id"]

        update_response = self.client.put(
            f"/api/blending/store-requests/{request_id}/",
            {
                "remarks": "Updated request",
                "request_type": "ADDITIVE",
                "request_date": "2026-05-22",
                "require_date": "2026-05-23",
                "require_time": "08:15:00",
                "requested_for_name": "Shift Lead",
                "request_reason": "Need both additives",
                "items": [
                    {"item_id": item_one.id, "quantity": "7.000", "remarks": "Increase quantity"},
                    {"item_id": item_two.id, "quantity": "3.500", "remarks": "Add second item"},
                ],
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["data"]["requested_for_name"], "Shift Lead")
        self.assertEqual(str(update_response.data["data"]["request_date"]), "2026-05-22")
        self.assertEqual(str(update_response.data["data"]["require_date"]), "2026-05-23")
        self.assertEqual(str(update_response.data["data"]["require_time"]), "08:15:00")
        self.assertEqual(len(update_response.data["data"]["items"]), 2)

        detail_response = self.client.get(f"/api/blending/store-requests/{request_id}/")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(len(detail_response.data["data"]["items"]), 2)
        self.assertEqual(detail_response.data["data"]["items"][0]["item"], item_one.id)
        self.assertEqual(detail_response.data["data"]["items"][1]["item"], item_two.id)

    def test_blending_stock_list_reads_store_inventory_for_blending_warehouse(self):
        item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Mixer Additive",
            unit="kg",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.blending_warehouse,
            quantity="10.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="BLEND-IN-1",
            created_by=self.store_user,
        )

        response = self.client.get("/api/blending/stock/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(response.data["data"]["results"][0]["quantity"], "10.000")

    def test_requestable_additive_stock_list_reads_store_inventory_for_dropdown(self):
        additive_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Processing Additive A",
            unit="kg",
        )
        non_additive_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="lldpe",
            item_name="LLDPE Resin",
            unit="kg",
        )
        apply_inward_stock(
            item=additive_item,
            warehouse=self.store_warehouse,
            quantity="25.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-ADD-1",
            created_by=self.store_user,
        )
        apply_inward_stock(
            item=non_additive_item,
            warehouse=self.store_warehouse,
            quantity="40.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-RM-1",
            created_by=self.store_user,
        )

        response = self.client.get("/api/blending/requestable-additive-stock/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 2)
        self.assertEqual(
            {row["item"] for row in response.data["data"]["results"]},
            {additive_item.id, non_additive_item.id},
        )
        self.assertEqual(
            {row["warehouse_code"] for row in response.data["data"]["results"]},
            {self.store_warehouse.code},
        )

    def test_requestable_additive_stock_list_includes_zero_balance_items_as_read_only_rows(self):
        available_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Available Item",
            unit="kg",
        )
        zero_balance_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="lldpe",
            item_name="Zero Balance Item",
            unit="kg",
        )
        apply_inward_stock(
            item=available_item,
            warehouse=self.store_warehouse,
            quantity="4.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-ALL-1",
            created_by=self.store_user,
        )
        apply_inward_stock(
            item=zero_balance_item,
            warehouse=self.store_warehouse,
            quantity="2.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-ALL-2",
            created_by=self.store_user,
        )
        apply_outward_stock(
            item=zero_balance_item,
            warehouse=self.store_warehouse,
            quantity="2.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_OUTWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-ALL-3",
            created_by=self.store_user,
        )

        response = self.client.get("/api/blending/requestable-additive-stock/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 2)
        quantity_by_item = {
            row["item"]: row["quantity"]
            for row in response.data["data"]["results"]
        }
        self.assertEqual(quantity_by_item[available_item.id], "4.000")
        self.assertEqual(quantity_by_item[zero_balance_item.id], "0.000")

    def test_blending_stock_list_supports_requestable_additive_scope(self):
        additive_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Mixer Additive",
            unit="kg",
        )
        non_additive_item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="hdpe",
            item_name="Scope Resin",
            unit="kg",
        )
        apply_inward_stock(
            item=additive_item,
            warehouse=self.store_warehouse,
            quantity="15.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-ADD-2",
            created_by=self.store_user,
        )
        apply_inward_stock(
            item=non_additive_item,
            warehouse=self.store_warehouse,
            quantity="5.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="STORE-RM-2",
            created_by=self.store_user,
        )

        response = self.client.get("/api/blending/stock/?stock_scope=requestable")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 2)
        self.assertEqual(
            {row["item"] for row in response.data["data"]["results"]},
            {additive_item.id, non_additive_item.id},
        )
        self.assertEqual(
            {row["warehouse_code"] for row in response.data["data"]["results"]},
            {self.store_warehouse.code},
        )

    def test_blending_user_cannot_approve_requests(self):
        item = Item.objects.create(
            category="Raw Material",
            group="polymer",
            sub_group="lldpe",
            item_name="LLDPE Resin",
            unit="kg",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.store_warehouse,
            quantity="10.000",
            transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
            reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
            reference_id="OPEN-4",
            created_by=self.store_user,
        )
        request_response = self.client.post(
            "/api/blending/store-requests/",
            {"items": [{"item_id": item.id, "quantity": "2.000"}]},
            format="json",
        )
        request_id = request_response.data["data"]["id"]

        approve_response = self.client.post(
            f"/api/store/requests/{request_id}/approve/",
            {"approval_remarks": "Should not be allowed"},
            format="json",
        )

        self.assertEqual(approve_response.status_code, 403)

    def test_blending_inventory_summary_api_returns_current_stock_totals(self):
        primary_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="mix additive",
            item_name="Primary Blending Item",
            unit="kg",
        )
        secondary_item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="processing additive",
            item_name="Secondary Blending Item",
            unit="kg",
        )
        apply_inward_stock(
            item=primary_item,
            warehouse=self.blending_warehouse,
            quantity="8.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="BLEND-IN-1",
            created_by=self.store_user,
            transaction_date="2026-05-08",
        )
        apply_outward_stock(
            item=primary_item,
            warehouse=self.blending_warehouse,
            quantity="2.500",
            transaction_type=StoreTransaction.TransactionType.MANUAL_OUTWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="BLEND-OUT-1",
            created_by=self.store_user,
            transaction_date="2026-05-09",
        )
        apply_inward_stock(
            item=secondary_item,
            warehouse=self.blending_warehouse,
            quantity="6.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="BLEND-IN-2",
            created_by=self.store_user,
            transaction_date="2026-05-01",
        )

        summary_response = self.client.get(
            f"/api/blending/inventory/summary/?item_id={primary_item.id}&search=Primary&page=1&page_size=10"
        )

        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.data["data"]["count"], 1)
        self.assertEqual(summary_response.data["data"]["results"][0]["item_id"], primary_item.id)
        self.assertEqual(summary_response.data["data"]["results"][0]["item_name"], primary_item.item_name)
        self.assertEqual(summary_response.data["data"]["results"][0]["total_inward"], "8.000")
        self.assertEqual(summary_response.data["data"]["results"][0]["total_outward"], "2.500")
        self.assertEqual(summary_response.data["data"]["results"][0]["current_stock"], "5.500")
        self.assertTrue(summary_response.data["data"]["results"][0]["last_updated"])

    def test_blending_inventory_history_api_returns_latest_first(self):
        item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="history additive",
            item_name="History Blending Item",
            unit="kg",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.blending_warehouse,
            quantity="5.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="BLEND-HIST-IN-1",
            created_by=self.store_user,
            transaction_date="2026-05-08",
        )
        apply_outward_stock(
            item=item,
            warehouse=self.blending_warehouse,
            quantity="1.500",
            transaction_type=StoreTransaction.TransactionType.MANUAL_OUTWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="BLEND-HIST-OUT-1",
            created_by=self.store_user,
            transaction_date="2026-05-09",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.blending_warehouse,
            quantity="2.000",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="BLEND-HIST-IN-2",
            created_by=self.store_user,
            transaction_date="2026-05-10",
        )

        response = self.client.get(f"/api/blending/inventory/{item.id}/history/?page=1&page_size=10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 3)
        latest_row = response.data["data"]["results"][0]
        self.assertEqual(latest_row["transaction_type"], "INWARD")
        self.assertEqual(latest_row["quantity"], "2.000")
        self.assertEqual(latest_row["opening_stock"], "3.500")
        self.assertEqual(latest_row["closing_stock"], "5.500")
        self.assertEqual(latest_row["reference_no"], "BLEND-HIST-IN-2")
        self.assertEqual(latest_row["module"], "MANUAL")
        self.assertEqual(latest_row["created_by"], self.store_user.username)

    def test_blending_inventory_legacy_monitoring_endpoints_are_removed(self):
        response = self.client.get("/api/blending/stock/current/")
        self.assertEqual(response.status_code, 404)

        response = self.client.post("/api/blending/stock/inward/", {}, format="json")
        self.assertEqual(response.status_code, 404)

        response = self.client.post("/api/blending/stock/outward/", {}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_blending_inventory_outward_rejects_quantity_above_current_stock(self):
        item = Item.objects.create(
            category="Additive",
            group="blend",
            sub_group="stabilizer",
            item_name="Constrained Blending Item",
            unit="kg",
        )
        apply_inward_stock(
            item=item,
            warehouse=self.blending_warehouse,
            quantity="1.500",
            transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
            reference_type=StoreTransaction.ReferenceType.MANUAL,
            reference_id="BLEND-IN-3",
            created_by=self.store_user,
            transaction_date="2026-05-12",
        )

        with self.assertRaises(ValidationError) as exc:
            apply_outward_stock(
                item=item,
                warehouse=self.blending_warehouse,
                quantity="2.000",
                transaction_type=StoreTransaction.TransactionType.MANUAL_OUTWARD,
                reference_type=StoreTransaction.ReferenceType.MANUAL,
                reference_id="BLEND-OUT-2",
                created_by=self.store_user,
                transaction_date="2026-05-12",
            )
        self.assertIn("quantity", exc.exception.detail)
