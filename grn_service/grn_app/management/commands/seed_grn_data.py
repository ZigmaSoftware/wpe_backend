from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from grn_app.models import GRN, GRNAuditLog, QCR


# ---------------------------------------------------------------------------
# Supplier catalogue
# ---------------------------------------------------------------------------
SUPPLIERS = {
    "SUP-001": {
        "supplier_id": "SUP-001",
        "gstin": "27AABCG1234F1Z5",
        "contact_name": "Arun Sharma",
        "trade_name": "Greenline Polymers Pvt Ltd",
        "contact_type": "Manufacturer",
        "address1": "Plot 12, MIDC Industrial Area",
        "address2": "Phase II",
        "location": "Pune",
        "pincode": "411019",
        "state_name": "Maharashtra",
        "state_code": "27",
        "country": "India",
        "person_name": "Arun Sharma",
        "phone_number": "+919876543210",
        "email": "arun.sharma@greenlinepolymers.in",
        "category": "Raw Material",
        "segment": "Polymer",
        "sub_segment": "Thermoplastic",
        "sales_contact_id": "SC-01",
        "currency": "INR",
    },
    "SUP-002": {
        "supplier_id": "SUP-002",
        "gstin": "33BBDCH5678G2Z6",
        "contact_name": "Priya Nair",
        "trade_name": "Wood Fibre House",
        "contact_type": "Trader",
        "address1": "No 7, Anna Salai",
        "address2": "Industrial Estate",
        "location": "Chennai",
        "pincode": "600002",
        "state_name": "Tamil Nadu",
        "state_code": "33",
        "country": "India",
        "person_name": "Priya Nair",
        "phone_number": "+919988776655",
        "email": "priya@woodfibrehouse.com",
        "category": "Raw Material",
        "segment": "Natural Fibre",
        "sub_segment": "Wood",
        "sales_contact_id": "SC-02",
        "currency": "INR",
    },
    "SUP-003": {
        "supplier_id": "SUP-003",
        "gstin": "29CCECI9012H3Z7",
        "contact_name": "Suresh Patel",
        "trade_name": "Additives India Ltd",
        "contact_type": "Manufacturer",
        "address1": "Block B, KIADB",
        "address2": "Peenya Industrial Area",
        "location": "Bengaluru",
        "pincode": "560058",
        "state_name": "Karnataka",
        "state_code": "29",
        "country": "India",
        "person_name": "Suresh Patel",
        "phone_number": "+919845671234",
        "email": "suresh@additivesindia.com",
        "category": "Additive",
        "segment": "Chemical",
        "sub_segment": "Stabiliser",
        "sales_contact_id": "SC-03",
        "currency": "INR",
    },
    "SUP-004": {
        "supplier_id": "SUP-004",
        "gstin": "24DDDJ3456I4Z8",
        "contact_name": "Mehul Shah",
        "trade_name": "Catalyst Additives Co",
        "contact_type": "Manufacturer",
        "address1": "Survey 88, GIDC Estate",
        "address2": "",
        "location": "Surat",
        "pincode": "394210",
        "state_name": "Gujarat",
        "state_code": "24",
        "country": "India",
        "person_name": "Mehul Shah",
        "phone_number": "+919727384950",
        "email": "mehul@catalystadditives.com",
        "category": "Additive",
        "segment": "Chemical",
        "sub_segment": "Catalyst",
        "sales_contact_id": "SC-04",
        "currency": "INR",
    },
    "SUP-005": {
        "supplier_id": "SUP-005",
        "gstin": "06EEFK7890J5Z9",
        "contact_name": "Deepak Verma",
        "trade_name": "ElectroParts Solutions",
        "contact_type": "Distributor",
        "address1": "Sector 29, Industrial Model Township",
        "address2": "",
        "location": "Faridabad",
        "pincode": "121001",
        "state_name": "Haryana",
        "state_code": "06",
        "country": "India",
        "person_name": "Deepak Verma",
        "phone_number": "+919811234567",
        "email": "deepak@electroparts.in",
        "category": "Spare Parts",
        "segment": "Electrical",
        "sub_segment": "Automation",
        "sales_contact_id": "SC-05",
        "currency": "INR",
    },
    "SUP-006": {
        "supplier_id": "SUP-006",
        "gstin": "09FFFM2345K6Z1",
        "contact_name": "Anita Singh",
        "trade_name": "MechPro Industries",
        "contact_type": "Manufacturer",
        "address1": "Industrial Area Phase III",
        "address2": "Kanpur Road",
        "location": "Lucknow",
        "pincode": "226012",
        "state_name": "Uttar Pradesh",
        "state_code": "09",
        "country": "India",
        "person_name": "Anita Singh",
        "phone_number": "+919839876543",
        "email": "anita@mechpro.in",
        "category": "Spare Parts",
        "segment": "Mechanical",
        "sub_segment": "Bearings & Seals",
        "sales_contact_id": "SC-06",
        "currency": "INR",
    },
}

# ---------------------------------------------------------------------------
# GRN catalogue  – all lifecycle stages represented
# ---------------------------------------------------------------------------
GRN_RECORDS = [
    # ── Active (GRN Process) ──────────────────────────────────────────────
    {
        "grn_no": "GRN-2026-001",
        "po_no": "PO-2026-011",
        "po_date": date(2026, 4, 20),
        "grn_date": date(2026, 5, 2),
        "supplier_key": "SUP-001",
        "invoice_no": "INV-GLP-4501",
        "invoice_date": date(2026, 5, 1),
        "gate_entry_no": "GE-0011",
        "gate_entry_date": date(2026, 5, 2),
        "req_department": "Production",
        "req_person": "Raju Menon",
        "req_person_id": "EMP-201",
        "req_reason": "Monthly HDPE stock replenishment for production line A.",
        "items": [
            {
                "item_id": "ITM-P001",
                "item_serial_number": 1,
                "product_description": "HDPE Natural Granules Grade F46003",
                "hsn_code": "39011090",
                "quantity": "500.00",
                "unit": "KG",
                "unit_price": "92.00",
                "gst_rate": "18.00",
            },
            {
                "item_id": "ITM-P002",
                "item_serial_number": 2,
                "product_description": "HDPE Black Masterbatch MB-400",
                "hsn_code": "32151900",
                "quantity": "50.00",
                "unit": "KG",
                "unit_price": "140.00",
                "gst_rate": "18.00",
            },
        ],
        "freight_charge": "850.00",
        "process_status": "GRN Process",
        "warehouse": "QC Pending Warehouse - CBE",
        "accepted_warehouse": "Stores",
        "rejected_warehouse": "Rejected Warehouse - CBE",
    },
    {
        "grn_no": "GRN-2026-002",
        "po_no": "PO-2026-012",
        "po_date": date(2026, 4, 22),
        "grn_date": date(2026, 5, 3),
        "supplier_key": "SUP-002",
        "invoice_no": "INV-WFH-891",
        "invoice_date": date(2026, 5, 2),
        "gate_entry_no": "GE-0012",
        "gate_entry_date": date(2026, 5, 3),
        "req_department": "Production",
        "req_person": "Kavitha Rajan",
        "req_person_id": "EMP-202",
        "req_reason": "Wood flour for composite extrusion batch Q2.",
        "items": [
            {
                "item_id": "ITM-W001",
                "item_serial_number": 1,
                "product_description": "Wood Flour 80 Mesh - Pine",
                "hsn_code": "44013000",
                "quantity": "800.00",
                "unit": "KG",
                "unit_price": "18.50",
                "gst_rate": "5.00",
            },
        ],
        "freight_charge": "600.00",
        "process_status": "GRN Process",
        "warehouse": "QC Pending Warehouse - CBE",
        "accepted_warehouse": "Stores",
        "rejected_warehouse": "Rejected Warehouse - CBE",
    },
    {
        "grn_no": "GRN-2026-003",
        "po_no": "PO-2026-013",
        "po_date": date(2026, 4, 25),
        "grn_date": date(2026, 5, 4),
        "supplier_key": "SUP-005",
        "invoice_no": "INV-EP-2201",
        "invoice_date": date(2026, 5, 3),
        "gate_entry_no": "GE-0013",
        "gate_entry_date": date(2026, 5, 4),
        "req_department": "Maintenance",
        "req_person": "Santhosh Kumar",
        "req_person_id": "EMP-301",
        "req_reason": "Replacement sensors and contactors for production line maintenance.",
        "items": [
            {
                "item_id": "ITM-E001",
                "item_serial_number": 1,
                "product_description": "Proximity Sensor NPN 12-24V DC",
                "hsn_code": "85369090",
                "quantity": "20.00",
                "unit": "NOS",
                "unit_price": "850.00",
                "gst_rate": "18.00",
            },
            {
                "item_id": "ITM-E002",
                "item_serial_number": 2,
                "product_description": "AC Contactor 40A 3 Pole",
                "hsn_code": "85365019",
                "quantity": "10.00",
                "unit": "NOS",
                "unit_price": "1200.00",
                "gst_rate": "18.00",
            },
        ],
        "freight_charge": "350.00",
        "process_status": "GRN Process",
        "warehouse": "QC Pending Warehouse - CBE",
        "accepted_warehouse": "Maintenance Store",
        "rejected_warehouse": "Rejected Warehouse - CBE",
    },
    # ── Moved to QCR (awaiting inspection) ───────────────────────────────
    {
        "grn_no": "GRN-2026-004",
        "po_no": "PO-2026-007",
        "po_date": date(2026, 4, 10),
        "grn_date": date(2026, 4, 22),
        "supplier_key": "SUP-004",
        "invoice_no": "INV-CAT-1190",
        "invoice_date": date(2026, 4, 21),
        "gate_entry_no": "GE-0007",
        "gate_entry_date": date(2026, 4, 22),
        "req_department": "Production",
        "req_person": "Mani Prasad",
        "req_person_id": "EMP-203",
        "req_reason": "Catalyst pack for May production batch.",
        "items": [
            {
                "item_id": "ITM-C001",
                "item_serial_number": 1,
                "product_description": "Processing Additive Pack - Heat Stabiliser HS-400",
                "hsn_code": "38123090",
                "quantity": "60.00",
                "unit": "KG",
                "unit_price": "310.00",
                "gst_rate": "18.00",
            },
        ],
        "freight_charge": "400.00",
        "process_status": "Moved to QCR",
        "warehouse": "QC Pending Warehouse - CBE",
        "accepted_warehouse": "Stores",
        "rejected_warehouse": "Rejected Warehouse - CBE",
        "moved_to_qcr_hours_ago": 8,
    },
    {
        "grn_no": "GRN-2026-005",
        "po_no": "PO-2026-008",
        "po_date": date(2026, 4, 12),
        "grn_date": date(2026, 4, 24),
        "supplier_key": "SUP-006",
        "invoice_no": "INV-MP-3302",
        "invoice_date": date(2026, 4, 23),
        "gate_entry_no": "GE-0008",
        "gate_entry_date": date(2026, 4, 24),
        "req_department": "Engineering",
        "req_person": "Vasanth Rao",
        "req_person_id": "EMP-401",
        "req_reason": "Bearings and seals for quarterly preventive maintenance.",
        "items": [
            {
                "item_id": "ITM-M001",
                "item_serial_number": 1,
                "product_description": "Deep Groove Ball Bearing 6205-2RS",
                "hsn_code": "84821010",
                "quantity": "48.00",
                "unit": "NOS",
                "unit_price": "220.00",
                "gst_rate": "18.00",
            },
            {
                "item_id": "ITM-M002",
                "item_serial_number": 2,
                "product_description": "Oil Seal TC 40x60x10",
                "hsn_code": "40169300",
                "quantity": "30.00",
                "unit": "NOS",
                "unit_price": "85.00",
                "gst_rate": "18.00",
            },
        ],
        "freight_charge": "280.00",
        "process_status": "Moved to QCR",
        "warehouse": "QC Pending Warehouse - CBE",
        "accepted_warehouse": "Engineering Store",
        "rejected_warehouse": "Rejected Warehouse - CBE",
        "moved_to_qcr_hours_ago": 5,
    },
    # ── GRN Approved (passed QC, stock added to store) ────────────────────
    {
        "grn_no": "GRN-2026-006",
        "po_no": "PO-2026-003",
        "po_date": date(2026, 3, 28),
        "grn_date": date(2026, 4, 8),
        "supplier_key": "SUP-001",
        "invoice_no": "INV-GLP-4210",
        "invoice_date": date(2026, 4, 7),
        "gate_entry_no": "GE-0003",
        "gate_entry_date": date(2026, 4, 8),
        "req_department": "Production",
        "req_person": "Raju Menon",
        "req_person_id": "EMP-201",
        "req_reason": "April production LDPE requirement.",
        "items": [
            {
                "item_id": "ITM-P003",
                "item_serial_number": 1,
                "product_description": "LDPE Film Grade Granules 150 BW",
                "hsn_code": "39011010",
                "quantity": "300.00",
                "unit": "KG",
                "unit_price": "105.00",
                "gst_rate": "18.00",
            },
        ],
        "freight_charge": "700.00",
        "process_status": "GRN Approved",
        "warehouse": "QC Pending Warehouse - CBE",
        "accepted_warehouse": "Stores",
        "rejected_warehouse": "Rejected Warehouse - CBE",
        "moved_to_qcr_hours_ago": 72,
        "qcr_status": "Moved to GRN",
        "qcr_remarks": None,
    },
    {
        "grn_no": "GRN-2026-007",
        "po_no": "PO-2026-004",
        "po_date": date(2026, 3, 30),
        "grn_date": date(2026, 4, 10),
        "supplier_key": "SUP-003",
        "invoice_no": "INV-AI-8801",
        "invoice_date": date(2026, 4, 9),
        "gate_entry_no": "GE-0004",
        "gate_entry_date": date(2026, 4, 10),
        "req_department": "Quality",
        "req_person": "Bhavana Krishnan",
        "req_person_id": "EMP-501",
        "req_reason": "Anti-oxidant restock for quality lab use.",
        "items": [
            {
                "item_id": "ITM-A001",
                "item_serial_number": 1,
                "product_description": "Anti-Oxidant AO-1010 Powder",
                "hsn_code": "29071900",
                "quantity": "25.00",
                "unit": "KG",
                "unit_price": "2100.00",
                "gst_rate": "18.00",
            },
        ],
        "freight_charge": "200.00",
        "process_status": "GRN Approved",
        "warehouse": "QC Pending Warehouse - CBE",
        "accepted_warehouse": "Quality Store",
        "rejected_warehouse": "Rejected Warehouse - CBE",
        "moved_to_qcr_hours_ago": 96,
        "qcr_status": "Moved to GRN",
        "qcr_remarks": None,
    },
    {
        "grn_no": "GRN-2026-008",
        "po_no": "PO-2026-005",
        "po_date": date(2026, 4, 1),
        "grn_date": date(2026, 4, 14),
        "supplier_key": "SUP-005",
        "invoice_no": "INV-EP-2100",
        "invoice_date": date(2026, 4, 13),
        "gate_entry_no": "GE-0005",
        "gate_entry_date": date(2026, 4, 14),
        "req_department": "Maintenance",
        "req_person": "Santhosh Kumar",
        "req_person_id": "EMP-301",
        "req_reason": "VFD drives for upgraded conveyor system.",
        "items": [
            {
                "item_id": "ITM-E003",
                "item_serial_number": 1,
                "product_description": "Variable Frequency Drive 2.2KW 415V 3Ph",
                "hsn_code": "85044019",
                "quantity": "4.00",
                "unit": "NOS",
                "unit_price": "8500.00",
                "gst_rate": "18.00",
            },
        ],
        "freight_charge": "500.00",
        "process_status": "GRN Approved",
        "warehouse": "QC Pending Warehouse - CBE",
        "accepted_warehouse": "Maintenance Store",
        "rejected_warehouse": "Rejected Warehouse - CBE",
        "moved_to_qcr_hours_ago": 120,
        "qcr_status": "Moved to GRN",
        "qcr_remarks": None,
    },
    # ── Rejected (QC failed, stock not moved to store) ────────────────────
    {
        "grn_no": "GRN-2026-009",
        "po_no": "PO-2026-006",
        "po_date": date(2026, 4, 5),
        "grn_date": date(2026, 4, 18),
        "supplier_key": "SUP-003",
        "invoice_no": "INV-AI-8650",
        "invoice_date": date(2026, 4, 17),
        "gate_entry_no": "GE-0006",
        "gate_entry_date": date(2026, 4, 18),
        "req_department": "Production",
        "req_person": "Mani Prasad",
        "req_person_id": "EMP-203",
        "req_reason": "Coupling agent for WPC formulation batch.",
        "items": [
            {
                "item_id": "ITM-A002",
                "item_serial_number": 1,
                "product_description": "Maleic Anhydride Grafted PP Coupling Agent",
                "hsn_code": "39062000",
                "quantity": "50.00",
                "unit": "KG",
                "unit_price": "480.00",
                "gst_rate": "18.00",
            },
        ],
        "freight_charge": "300.00",
        "process_status": "Rejected",
        "warehouse": "QC Pending Warehouse - CBE",
        "accepted_warehouse": "Stores",
        "rejected_warehouse": "Rejected Warehouse - CBE",
        "moved_to_qcr_hours_ago": 144,
        "qcr_status": "Rejected",
        "qcr_remarks": "Sample failed melt flow index test. MFI observed: 28 g/10 min against required 18–22 g/10 min. Batch does not meet specification. Returned to supplier.",
    },
    {
        "grn_no": "GRN-2026-010",
        "po_no": "PO-2026-009",
        "po_date": date(2026, 4, 15),
        "grn_date": date(2026, 4, 28),
        "supplier_key": "SUP-006",
        "invoice_no": "INV-MP-3100",
        "invoice_date": date(2026, 4, 27),
        "gate_entry_no": "GE-0009",
        "gate_entry_date": date(2026, 4, 28),
        "req_department": "Engineering",
        "req_person": "Vasanth Rao",
        "req_person_id": "EMP-401",
        "req_reason": "Replacement V-belts for extrusion drive system.",
        "items": [
            {
                "item_id": "ITM-M003",
                "item_serial_number": 1,
                "product_description": "V-Belt B-Section B78 - Industrial Grade",
                "hsn_code": "40103100",
                "quantity": "24.00",
                "unit": "NOS",
                "unit_price": "350.00",
                "gst_rate": "18.00",
            },
        ],
        "freight_charge": "150.00",
        "process_status": "Rejected",
        "warehouse": "QC Pending Warehouse - CBE",
        "accepted_warehouse": "Engineering Store",
        "rejected_warehouse": "Rejected Warehouse - CBE",
        "moved_to_qcr_hours_ago": 60,
        "qcr_status": "Rejected",
        "qcr_remarks": "Incorrect belt section supplied — B78 received instead of ordered A78. Physical dimensions do not fit existing drives. Purchase team notified for re-order.",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calc_item(item: dict) -> dict:
    qty = Decimal(item["quantity"])
    unit_price = Decimal(item["unit_price"])
    gst_rate = Decimal(item["gst_rate"])
    total_amount = (qty * unit_price).quantize(Decimal("0.01"))
    gst_amount = (total_amount * gst_rate / 100).quantize(Decimal("0.01"))
    half_gst = (gst_amount / 2).quantize(Decimal("0.01"))
    total_item_value = (total_amount + gst_amount).quantize(Decimal("0.01"))
    return {
        "item_id": item["item_id"],
        "item_serial_number": item["item_serial_number"],
        "product_description": item["product_description"],
        "hsn_code": item["hsn_code"],
        "total_quantity": str(qty),
        "quantity": str(qty),
        "free_quantity": "0.00",
        "accepted_qty": str(qty),
        "rejected_qty": "0.00",
        "unit": item["unit"],
        "unit_price": str(unit_price),
        "total_amount": str(total_amount),
        "discount": "0",
        "assessable_value": str(total_amount),
        "gst_rate": str(gst_rate),
        "igst_amount": "0.00",
        "cgst_amount": str(half_gst),
        "sgst_amount": str(half_gst),
        "total_item_value": str(total_item_value),
        # keep originals for model fields
        "_total_amount_d": total_amount,
        "_gst_amount_d": gst_amount,
        "_total_item_value_d": total_item_value,
    }


def _build_payload(rec: dict) -> dict:
    sup = SUPPLIERS[rec["supplier_key"]]
    calc_items = [_calc_item(it) for it in rec["items"]]

    total_before_tax = sum(i["_total_amount_d"] for i in calc_items)
    total_tax = sum(i["_gst_amount_d"] for i in calc_items)
    freight = Decimal(rec["freight_charge"])
    total_after_tax = (total_before_tax + total_tax + freight).quantize(Decimal("0.01"))

    clean_items = [{k: v for k, v in i.items() if not k.startswith("_")} for i in calc_items]

    payload = {
        "document_details": {
            "po_no": rec["po_no"],
            "po_date": rec["po_date"].isoformat(),
            "grn_no": rec["grn_no"],
            "grn_date": rec["grn_date"].isoformat(),
            "supplier_invoice_no": rec["invoice_no"],
            "supplier_invoice_date": rec["invoice_date"].isoformat(),
            "gateentry_bookno": rec["gate_entry_no"],
            "gateentry_bookdate": rec["gate_entry_date"].isoformat(),
            "tolerance": "2%",
        },
        "document_requirement_details": {
            "req_date": rec["grn_date"].isoformat(),
            "req_person_name": rec["req_person"],
            "req_person_id": rec["req_person_id"],
            "req_department": rec["req_department"],
            "req_reason": rec["req_reason"],
        },
        "supplier_details": deepcopy(sup),
        "items": clean_items,
        "value_details": {
            "freight_charge": rec["freight_charge"],
            "loading_unloading_charge": "150.00",
            "total_before_tax": str(total_before_tax),
            "total_tax_amount": str(total_tax),
            "total_after_tax": str(total_after_tax),
        },
    }
    return payload, total_before_tax, total_tax, total_after_tax, calc_items


class Command(BaseCommand):
    help = "Seed comprehensive GRN/QCR demo data covering all lifecycle stages."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing GRN/QCR/AuditLog records before seeding.",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing existing GRN data...")
            GRNAuditLog.objects.all().delete()
            QCR.objects.all().delete()
            GRN.objects.all().delete()
            self.stdout.write(self.style.WARNING("All GRN records deleted."))

        created = updated = 0
        with transaction.atomic():
            for rec in GRN_RECORDS:
                did_create = self._seed_grn_record(rec)
                if did_create:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {created} created, {updated} updated. "
                f"Total GRN: {GRN.objects.count()}, QCR: {QCR.objects.count()}."
            )
        )

    # ------------------------------------------------------------------
    def _seed_grn_record(self, rec: dict) -> bool:
        payload, total_before_tax, total_tax, total_after_tax, calc_items = _build_payload(rec)
        sup = SUPPLIERS[rec["supplier_key"]]
        first = calc_items[0]
        hours_ago = rec.get("moved_to_qcr_hours_ago", 0)
        moved_at = timezone.now() - timedelta(hours=hours_ago) if hours_ago else None
        is_moved = rec["process_status"] not in ("GRN Process",)

        defaults = {
            "po_no": rec["po_no"],
            "po_date": rec["po_date"],
            "grn_date": rec["grn_date"],
            "supplier_invoice_no": rec["invoice_no"],
            "supplier_invoice_date": rec["invoice_date"],
            "gateentry_bookno": rec["gate_entry_no"],
            "gateentry_bookdate": rec["gate_entry_date"],
            "tolerance": "2%",
            "req_date": rec["grn_date"].isoformat(),
            "req_person_name": rec["req_person"],
            "req_person_id": rec["req_person_id"],
            "req_department": rec["req_department"],
            "req_reason": rec["req_reason"],
            "supplier_id": sup["supplier_id"],
            "gstin": sup["gstin"],
            "contact_name": sup["contact_name"],
            "trade_name": sup["trade_name"],
            "contact_type": sup["contact_type"],
            "address1": sup["address1"],
            "address2": sup["address2"],
            "location": sup["location"],
            "pincode": sup["pincode"],
            "state_name": sup["state_name"],
            "state_code": sup["state_code"],
            "country": sup["country"],
            "person_name": sup["person_name"],
            "phone_number": sup["phone_number"],
            "email": sup["email"],
            "category": sup["category"],
            "segment": sup["segment"],
            "sub_segment": sup["sub_segment"],
            "sales_contact_id": sup["sales_contact_id"],
            "currency": sup["currency"],
            "item_id": first["item_id"],
            "item_serial_number": int(first["item_serial_number"]),
            "product_description": first["product_description"],
            "hsn_code": first["hsn_code"],
            "total_quantity": Decimal(first["total_quantity"]),
            "quantity": Decimal(first["quantity"]),
            "free_quantity": Decimal("0.00"),
            "accepted_qty": Decimal(first["accepted_qty"]),
            "rejected_qty": Decimal("0.00"),
            "unit": first["unit"],
            "unit_price": Decimal(first["unit_price"]),
            "total_amount": Decimal(first["total_amount"]),
            "discount": "0",
            "assessable_value": Decimal(first["assessable_value"]),
            "gst_rate": Decimal(first["gst_rate"]),
            "igst_amount": Decimal("0.00"),
            "cgst_amount": Decimal(first["cgst_amount"]),
            "sgst_amount": Decimal(first["sgst_amount"]),
            "total_item_value": Decimal(first["total_item_value"]),
            "freight_charge": Decimal(rec["freight_charge"]),
            "loading_unloading_charge": "150.00",
            "total_before_tax": total_before_tax,
            "total_tax_amount": total_tax,
            "total_after_tax": total_after_tax,
            "grn_warehouse": rec.get("warehouse", "QC Pending Warehouse - CBE"),
            "accepted_warehouse": rec.get("accepted_warehouse", "Stores"),
            "rejected_warehouse": rec.get("rejected_warehouse", "Rejected Warehouse - CBE"),
            "raw_payload": payload,
            "process_status": rec["process_status"],
            "qc_status": self._derive_qc_status(rec["process_status"]),
            "status": rec["process_status"] == "GRN Approved",
            "moved_to_qcr_at": moved_at,
            "moved_to_qcr_by": "admin" if is_moved else None,
        }

        grn, created = GRN.objects.update_or_create(grn_no=rec["grn_no"], defaults=defaults)

        # Audit log
        GRNAuditLog.objects.get_or_create(
            grn=grn,
            stage=GRNAuditLog.STAGE_GRN_CREATED,
            defaults={"actor": "admin", "notes": f"GRN {grn.grn_no} seeded by demo script."},
        )

        # QCR records for moved/approved/rejected
        qcr_status = rec.get("qcr_status")
        if qcr_status:
            self._upsert_qcr(
                grn=grn,
                status=qcr_status,
                moved_at=moved_at,
                remarks=rec.get("qcr_remarks"),
            )
        elif rec["process_status"] == "Moved to QCR":
            self._upsert_qcr(grn=grn, status="Active", moved_at=moved_at, remarks=None)

        return created

    def _upsert_qcr(self, *, grn: GRN, status: str, moved_at, remarks):
        snapshot = {
            "grn_no": grn.grn_no,
            "po_no": grn.po_no,
            "supplier_id": grn.supplier_id,
            "trade_name": grn.trade_name,
            "product_description": grn.product_description,
            "req_department": grn.req_department,
            "accepted_qty": str(grn.accepted_qty) if grn.accepted_qty is not None else None,
            "quantity": str(grn.quantity) if grn.quantity is not None else None,
            "total_after_tax": str(grn.total_after_tax) if grn.total_after_tax is not None else None,
            "process_status": grn.process_status,
        }
        qcr, _ = QCR.objects.update_or_create(
            source_grn=grn,
            defaults={
                "grn_reference_no": grn.grn_no,
                "snapshot": snapshot,
                "status": status,
                "remarks": remarks,
                "moved_to_qcr_at": moved_at or timezone.now(),
                "moved_to_qcr_by": "admin",
            },
        )

        # Audit log for QCR actions
        if status == "Moved to GRN":
            GRNAuditLog.objects.get_or_create(
                grn=grn,
                stage=GRNAuditLog.STAGE_QCR_ACCEPTED,
                defaults={
                    "actor": "admin",
                    "notes": f"QC Pass. Accepted quantity moved to {grn.accepted_warehouse or 'Stores'}.",
                },
            )
            GRNAuditLog.objects.get_or_create(
                grn=grn,
                stage=GRNAuditLog.STAGE_ADDED_TO_STORE,
                defaults={
                    "actor": "admin",
                    "notes": f"Inventory posted to {grn.accepted_warehouse or 'Stores'}.",
                },
            )
        elif status == "Rejected":
            GRNAuditLog.objects.get_or_create(
                grn=grn,
                stage=GRNAuditLog.STAGE_QCR_REJECTED,
                defaults={
                    "actor": "admin",
                    "notes": f"QC Fail. Remarks: {remarks}",
                },
            )
        elif status == "Active":
            GRNAuditLog.objects.get_or_create(
                grn=grn,
                stage=GRNAuditLog.STAGE_MOVED_TO_QCR,
                defaults={
                    "actor": "admin",
                    "notes": f"Moved to QCR. QCR ID: {qcr.unique_id}",
                },
            )

        return qcr

    @staticmethod
    def _derive_qc_status(process_status: str) -> str:
        mapping = {
            "GRN Process": "Pending",
            "Moved to QCR": "Pending",
            "GRN Approved": "Pass",
            "Rejected": "Fail",
        }
        return mapping.get(process_status, "Pending")
