from __future__ import annotations

from decimal import Decimal
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.contacts.models import Contact
from apps.items.models import Item
from apps.presales.models import PreSales
from apps.store.models import StoreTransaction
from apps.store.services import (
    apply_inward_stock,
    apply_outward_stock,
    get_blending_warehouse,
    get_store_warehouse,
    transfer_stock,
)


CONTACTS = [
    {
        "name": "Aarav Buildtech",
        "phone": "+919876543210",
        "email": "aarav@buildtech.in",
        "category": Contact.Category.CUSTOMER,
        "company_name": "Aarav Buildtech Pvt Ltd",
        "gstin": "27ABCDE1234F1Z5",
        "state": "Maharashtra",
        "address": "Plot 12, MIDC, Pune",
        "lead_source": "Expo",
        "market_segment": "Infrastructure",
        "is_active": True,
    },
    {
        "name": "Greenline Polymers",
        "phone": "+919812345678",
        "email": "sales@greenlinepoly.com",
        "category": Contact.Category.SUPPLIER,
        "company_name": "Greenline Polymers",
        "gstin": "24ABCDE1234F1Z6",
        "state": "Gujarat",
        "address": "GIDC Industrial Area, Ahmedabad",
        "lead_source": "Referral",
        "market_segment": "Raw Materials",
        "is_active": True,
    },
    {
        "name": "Metro Pipes Lead",
        "phone": "+918888777666",
        "email": "ops@metropipes.in",
        "category": Contact.Category.LEAD,
        "company_name": "Metro Pipes",
        "gstin": None,
        "state": "Karnataka",
        "address": "Peenya, Bengaluru",
        "lead_source": "Website",
        "market_segment": "Retail",
        "is_active": True,
    },
]

ITEMS = [
    {
        "product_type": "General Item",
        "category": "Raw Material",
        "group": "Polymer",
        "sub_group": "HDPE",
        "item_name": "HDPE Natural Granules",
        "hsn_code": "39012000",
        "unit": "KG",
        "opening_stock": "1250.000",
        "product_details": "Primary polymer feedstock",
        "description": "Demo stock for inward and blending transfers",
        "min_max_status": True,
        "status": True,
        "date": "2026-05-01",
        "ref_id": "OPEN-HDPE-001",
        "trans_type": "opening stock",
        "contact": "System Seed",
        "warehouse": "STORE",
        "bin": "A1",
    },
    {
        "product_type": "General Item",
        "category": "Raw Material",
        "group": "Wood Flour",
        "sub_group": "Premium",
        "item_name": "Wood Flour 80 Mesh",
        "hsn_code": "44050010",
        "unit": "KG",
        "opening_stock": "980.000",
        "product_details": "Fine mesh wood flour",
        "description": "Demo stock for blending",
        "min_max_status": True,
        "status": True,
        "date": "2026-05-01",
        "ref_id": "OPEN-WOOD-001",
        "trans_type": "opening stock",
        "contact": "System Seed",
        "warehouse": "STORE",
        "bin": "B2",
    },
    {
        "product_type": "Profile Item",
        "category": "Finished Goods",
        "group": "Decking",
        "sub_group": "Premium",
        "item_name": "WPC Deck Board 146x24",
        "hsn_code": "39189090",
        "unit": "NOS",
        "opening_stock": "240.000",
        "product_details": "Demo finished goods item",
        "description": "Used for stock outward examples",
        "min_max_status": False,
        "status": True,
        "date": "2026-05-01",
        "ref_id": "OPEN-DECK-001",
        "trans_type": "opening stock",
        "contact": "System Seed",
        "warehouse": "STORE",
        "bin": "FG1",
    },
]

PRESALES = [
    {
        "order_code": "PS-2026-001",
        "stage": "Enquiry",
        "sale_type": "Project",
        "sale_category": "Primary",
        "project_name": "Metro Decking Package",
        "version_no": "V1",
        "description": "Demo presales enquiry for decking package",
        "lead_source": "Expo",
        "sale_contact": "Aarav Buildtech",
        "gp_percent": Decimal("18.50"),
        "gp_value": Decimal("185000.00"),
        "line_of_business": "Decking",
        "sub_segment": "Infrastructure",
        "segment_keyword": "premium",
        "required_date": "2026-06-15",
        "request_person_id": 101,
        "request_department": "Sales",
        "required_time_start": "10:00:00",
        "required_time_end": "18:00:00",
        "required_reason": "Budgetary estimate",
        "internal_ref_id": 5001,
        "invoice_ref_id": 9001,
        "tolerance": "2%",
        "profile_type": "Deck Board",
        "capex": "No",
        "tl_code": "TL-01",
        "delivery_challan_type": "Standard",
        "indent_number": "IND-001",
        "indent_date": "2026-05-02T10:30:00",
        "indent_receiving_datetime": "2026-05-02T11:00:00",
        "movement_description": "Demo movement description",
        "customer_po": "PO-DEMO-1001",
        "customer_po_date": "2026-05-03",
        "destination": "Pune Site",
        "document_contact": "Aarav Procurement Team",
        "previous_document_contact": "Legacy Contact",
        "base_order_id": 301,
        "base_customer_id": 401,
        "base_customer_name": "Aarav Buildtech Pvt Ltd",
        "base_order_date": "2026-05-01T09:30:00",
        "activity_id": 701,
    },
    {
        "order_code": "PS-2026-002",
        "stage": "Proposal",
        "sale_type": "Distribution",
        "sale_category": "Secondary",
        "project_name": "South Retail Expansion",
        "version_no": "V2",
        "description": "Demo distributor proposal",
        "lead_source": "Referral",
        "sale_contact": "Metro Pipes Lead",
        "gp_percent": Decimal("14.00"),
        "gp_value": Decimal("92000.00"),
        "line_of_business": "Profiles",
        "sub_segment": "Retail",
        "segment_keyword": "channel",
        "required_date": "2026-06-25",
        "request_person_id": 102,
        "request_department": "Sales",
        "required_time_start": "09:00:00",
        "required_time_end": "17:30:00",
        "required_reason": "Demo quote",
        "internal_ref_id": 5002,
        "invoice_ref_id": 9002,
        "tolerance": "3%",
        "profile_type": "Profile",
        "capex": "Yes",
        "tl_code": "TL-02",
        "delivery_challan_type": "Express",
        "indent_number": "IND-002",
        "indent_date": "2026-05-04T09:00:00",
        "indent_receiving_datetime": "2026-05-04T09:15:00",
        "movement_description": "Demo presales second record",
        "customer_po": "PO-DEMO-1002",
        "customer_po_date": "2026-05-04",
        "destination": "Bengaluru Hub",
        "document_contact": "Metro Commercial Team",
        "previous_document_contact": "Previous Metro Team",
        "base_order_id": 302,
        "base_customer_id": 402,
        "base_customer_name": "Metro Pipes",
        "base_order_date": "2026-05-02T12:00:00",
        "activity_id": 702,
    },
]


class Command(BaseCommand):
    help = "Seed demo data for core_system modules used by the frontend."

    def handle(self, *args, **options):
        with transaction.atomic():
            self.admin_user = self._seed_user()
            contacts = self._seed_contacts()
            items = self._seed_items()
            self._seed_stock_movements(items, contacts)
            self._seed_presales()

        self.stdout.write(self.style.SUCCESS("Core demo data seeded successfully."))

    def _seed_user(self):
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@gmail.com",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        if created or not user.check_password("admin@123"):
            user.set_password("admin@123")
            user.email = "admin@gmail.com"
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save()
        return user

    def _seed_contacts(self):
        records = []
        for payload in CONTACTS:
            record, _ = Contact.objects.update_or_create(
                phone=payload["phone"],
                defaults=payload,
            )
            records.append(record)
        return records

    def _seed_items(self):
        records = []
        store_warehouse = get_store_warehouse()
        for payload in ITEMS:
            item, _created = Item.objects.update_or_create(
                item_name=payload["item_name"],
                category=payload["category"],
                group=payload["group"],
                sub_group=payload["sub_group"],
                unit=payload["unit"],
                defaults={
                    "product_type": payload["product_type"],
                    "hsn_code": payload.get("hsn_code") or None,
                    "product_details": payload.get("product_details") or None,
                    "description": payload.get("description") or None,
                    "min_max_status": payload.get("min_max_status", False),
                    "status": payload.get("status", True),
                },
            )
            opening_stock = Decimal(str(payload.get("opening_stock") or "0"))
            reference_id = str(payload.get("ref_id") or f"OPEN-{item.id}")

            if opening_stock > 0 and not StoreTransaction.objects.filter(
                item=item,
                warehouse=store_warehouse,
                transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
                reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
                reference_id=reference_id,
            ).exists():
                apply_inward_stock(
                    item=item,
                    warehouse=store_warehouse,
                    quantity=opening_stock,
                    transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
                    reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
                    reference_id=reference_id,
                    remarks=payload.get("description"),
                    created_by=self.admin_user,
                    transaction_date=payload.get("date"),
                )
            records.append(item)
        return records

    def _seed_stock_movements(self, items, contacts):
        hdpe, wood_flour, deck_board = items
        store_warehouse = get_store_warehouse()
        blending_warehouse = get_blending_warehouse()

        if not StoreTransaction.objects.filter(reference_id="IN-HDPE-001").exists():
            apply_inward_stock(
                item=hdpe,
                warehouse=store_warehouse,
                quantity=Decimal("120.000"),
                transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
                reference_type=StoreTransaction.ReferenceType.MANUAL,
                reference_id="IN-HDPE-001",
                remarks=f"Seeded supplier receipt from {contacts[1].name}",
                metadata={
                    "doc_id": "PO-7781",
                    "contact": contacts[1].name,
                    "bin": "A1",
                },
                created_by=self.admin_user,
                transaction_date="2026-05-03",
            )

        if not StoreTransaction.objects.filter(reference_id="OUT-DECK-001").exists():
            apply_outward_stock(
                item=deck_board,
                warehouse=store_warehouse,
                quantity=Decimal("18.000"),
                transaction_type=StoreTransaction.TransactionType.MANUAL_OUTWARD,
                reference_type=StoreTransaction.ReferenceType.MANUAL,
                reference_id="OUT-DECK-001",
                remarks=f"Seeded sales issue for {contacts[0].name}",
                metadata={
                    "doc_id": "INV-2201",
                    "contact": contacts[0].name,
                    "bin": "FG1",
                },
                created_by=self.admin_user,
                transaction_date="2026-05-04",
            )

        if not StoreTransaction.objects.filter(reference_id="TRF-WOOD-001").exists():
            transfer_stock(
                item=wood_flour,
                quantity=Decimal("150.000"),
                source_warehouse=store_warehouse,
                destination_warehouse=blending_warehouse,
                reference_type=StoreTransaction.ReferenceType.ADJUSTMENT,
                reference_id="TRF-WOOD-001",
                remarks="Seeded transfer to blending",
                created_by=self.admin_user,
                transaction_date="2026-05-05",
            )

    def _seed_presales(self):
        for payload in PRESALES:
            normalized_payload = payload.copy()
            for field_name in ("indent_date", "indent_receiving_datetime", "base_order_date"):
                value = normalized_payload.get(field_name)
                if value:
                    normalized_payload[field_name] = timezone.make_aware(
                        datetime.fromisoformat(value),
                        timezone.get_current_timezone(),
                    )

            PreSales.objects.update_or_create(
                order_code=normalized_payload["order_code"],
                defaults=normalized_payload,
            )
