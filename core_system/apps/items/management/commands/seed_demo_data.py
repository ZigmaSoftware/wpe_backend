from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.contacts.models import Contact
from apps.items.models import Item
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

class Command(BaseCommand):
    help = "Seed demo data for core_system modules used by the frontend."

    def handle(self, *args, **options):
        with transaction.atomic():
            self.admin_user = self._seed_user()
            contacts = self._seed_contacts()
            items = self._seed_items()
            self._seed_stock_movements(items, contacts)

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
