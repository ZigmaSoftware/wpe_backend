from django.test import TestCase
from rest_framework.test import APIClient

from .models import GRN, QCR


class GRNQCRFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_moved_grn_is_removed_from_grn_list(self):
        grn = GRN.objects.create(grn_no="GRN-001")

        move_response = self.client.post(f"/api/grn/{grn.id}/move-to-qcr/", {}, format="json")

        self.assertEqual(move_response.status_code, 201)

        grn.refresh_from_db()
        self.assertFalse(grn.status)
        self.assertEqual(grn.process_status, "Moved to QCR")

        list_response = self.client.get("/api/grn/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json(), [])

    def test_qcr_move_to_grn_reenables_record_in_grn_list(self):
        grn = GRN.objects.create(grn_no="GRN-002", status=False, process_status="Moved to QCR")
        qcr = QCR.objects.create(
            source_grn=grn,
            grn_reference_no=grn.grn_no,
            snapshot={"grn_no": grn.grn_no},
            status="Active",
            moved_to_qcr_at=grn.created_at,
        )

        update_response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {"action": "move_to_grn"},
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)

        grn.refresh_from_db()
        qcr.refresh_from_db()
        self.assertTrue(grn.status)
        self.assertEqual(grn.process_status, "Moved to GRN")
        self.assertEqual(qcr.status, "Moved to GRN")

        list_response = self.client.get("/api/grn/")
        moved_grn_response = self.client.get("/api/grn/moved/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json(), [])
        self.assertEqual(moved_grn_response.status_code, 200)
        self.assertEqual(len(moved_grn_response.json()), 1)
        self.assertEqual(moved_grn_response.json()[0]["id"], grn.id)

        moved_response = self.client.get("/api/qcr/?tab=grn")

        self.assertEqual(moved_response.status_code, 200)
        self.assertEqual(len(moved_response.json()), 1)
        self.assertEqual(moved_response.json()[0]["id"], qcr.id)

    def test_qcr_list_shows_only_active_records_by_default(self):
        active_grn = GRN.objects.create(grn_no="GRN-003", status=False, process_status="Moved to QCR")
        active_qcr = QCR.objects.create(
            source_grn=active_grn,
            grn_reference_no=active_grn.grn_no,
            snapshot={"grn_no": active_grn.grn_no},
            status="Active",
            moved_to_qcr_at=active_grn.created_at,
        )

        moved_grn = GRN.objects.create(grn_no="GRN-004", status=True, process_status="Moved to GRN")
        QCR.objects.create(
            source_grn=moved_grn,
            grn_reference_no=moved_grn.grn_no,
            snapshot={"grn_no": moved_grn.grn_no},
            status="Moved to GRN",
            moved_to_qcr_at=moved_grn.created_at,
        )

        rejected_grn = GRN.objects.create(grn_no="GRN-005", status=False, process_status="Rejected")
        QCR.objects.create(
            source_grn=rejected_grn,
            grn_reference_no=rejected_grn.grn_no,
            snapshot={"grn_no": rejected_grn.grn_no},
            status="Rejected",
            moved_to_qcr_at=rejected_grn.created_at,
        )

        response = self.client.get("/api/qcr/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], active_qcr.id)

    def test_rejected_qcr_records_are_listed_in_cancelled_tab_view(self):
        grn = GRN.objects.create(grn_no="GRN-006", status=False, process_status="Moved to QCR")
        qcr = QCR.objects.create(
            source_grn=grn,
            grn_reference_no=grn.grn_no,
            snapshot={"grn_no": grn.grn_no},
            status="Active",
            moved_to_qcr_at=grn.created_at,
        )

        update_response = self.client.post(
            f"/api/qcr/{qcr.id}/status/",
            {"action": "reject"},
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)

        qcr_tab_response = self.client.get("/api/qcr/")
        cancelled_response = self.client.get("/api/qcr/?tab=cancelled")
        cancelled_route_response = self.client.get("/api/qcr/cancelled/")
        rejected_alias_response = self.client.get("/api/qcr/?status=rejected")

        self.assertEqual(qcr_tab_response.status_code, 200)
        self.assertEqual(qcr_tab_response.json(), [])
        self.assertEqual(cancelled_response.status_code, 200)
        self.assertEqual(len(cancelled_response.json()), 1)
        self.assertEqual(cancelled_response.json()[0]["id"], qcr.id)
        self.assertEqual(cancelled_route_response.status_code, 200)
        self.assertEqual(len(cancelled_route_response.json()), 1)
        self.assertEqual(cancelled_route_response.json()[0]["id"], qcr.id)
        self.assertEqual(rejected_alias_response.status_code, 200)
        self.assertEqual(len(rejected_alias_response.json()), 1)
        self.assertEqual(rejected_alias_response.json()[0]["id"], qcr.id)
