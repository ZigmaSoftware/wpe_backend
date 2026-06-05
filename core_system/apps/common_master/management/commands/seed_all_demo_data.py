from __future__ import annotations

import hashlib
from datetime import date, time, timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.admin_master.models import (
    MainScreen,
    Role,
    ScreenSection,
    Staff,
    TicketUserType,
    UserCreation,
    UserScreen,
    UserType,
    UserTypePermission,
    default_action_permissions,
)
from apps.blending.models import BlendingInward, BlendingOutward, BlendingStock
from apps.contacts.models import Contact
from apps.items.models import Item, ItemStockTransaction
from apps.login_home.models import Department
from apps.presales.models import PreSales, PresalesAuditLog, PresalesRequest, PresalesRequestItem
from apps.production.models import (
    BOMVariant,
    BOMVariantComponent,
    BatchWeightEntry,
    MaterialMovement,
    ProductionBatch,
    ProductionMachine,
    ProductionOrder,
    ProductionSummary,
    ProductionTransaction,
    RegrindMaterialEntry,
)
from apps.store.models import (
    StockRequest,
    StockRequestItem,
    StoreInward,
    StoreOutward,
    StoreTransaction,
    Warehouse,
)
from apps.store.services import (
    apply_inward_stock,
    apply_outward_stock,
    get_blending_warehouse,
    get_store_warehouse,
    transfer_stock,
)
from apps.wpe_masters.models import (
    BranchMaster,
    DepartmentMaster,
    LocationMaster,
    PriceBookMaster,
    ProductionTypeMaster,
    PurchaseTypeMaster,
    RoleMaster,
    SaleTypeMaster,
    WPERolePermission,
    WPEUserCreation,
    WPEUserScreenPermission,
    WarehouseMaster,
)

from ...models import (
    City,
    CommonMaster,
    Company,
    Continent,
    Country,
    Currency,
    Customer,
    CustomerAddress,
    CustomerBankDetail,
    CustomerContactPerson,
    CustomerDocument,
    CustomerStatutoryDetail,
    Project,
    State,
    Supplier,
    SupplierAddress,
    SupplierBankDetail,
    SupplierContactPerson,
    SupplierDocument,
    SupplierStatutoryDetail,
    Tax,
)


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin@123"


def money(value: str) -> Decimal:
    return Decimal(value)


def aware(days_offset: int = 0, hour: int = 10, minute: int = 0):
    base = timezone.datetime.combine(
        timezone.localdate() + timedelta(days=days_offset),
        time(hour, minute),
    )
    return timezone.make_aware(base, timezone.get_current_timezone())


def first_or_create(model_cls, lookup: dict[str, Any], defaults: dict[str, Any] | None = None):
    instance = model_cls.objects.filter(**lookup).first()
    if instance is None:
        return model_cls.objects.create(**lookup, **(defaults or {})), True

    changed = False
    for field_name, value in (defaults or {}).items():
        if getattr(instance, field_name) != value:
            setattr(instance, field_name, value)
            changed = True
    if changed:
        instance.save()
    return instance, False


class Command(BaseCommand):
    help = "Seed sample data across all WPE ERP custom app tables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-grn",
            action="store_true",
            help="Do not run the larger GRN/QCR seed command.",
        )
        parser.add_argument(
            "--flush-grn",
            action="store_true",
            help="Delete existing GRN/QCR demo records before seeding GRN data.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Seeding WPE ERP demo data...")

        with transaction.atomic():
            self.users = self._seed_users()
            self.departments = self._seed_departments()
            self.admin_master = self._seed_admin_master()
            self.common = self._seed_common_master()
            self.wpe_masters = self._seed_wpe_masters()
            self.parties = self._seed_parties()
            self.items = self._seed_items()
            self._seed_inventory()
            self._seed_contacts()
            self._seed_presales()
            self._seed_production()

        if not options["skip_grn"]:
            call_command("seed_grn_data", flush=options["flush_grn"], verbosity=options.get("verbosity", 1))

        self.stdout.write(self.style.SUCCESS("All demo data seeded successfully."))
        self.stdout.write(f"Login user: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")

    def _seed_users(self):
        user_model = get_user_model()
        users = {}
        for username, payload in {
            ADMIN_USERNAME: {
                "password": ADMIN_PASSWORD,
                "email": "admin@gmail.com",
                "is_staff": True,
                "is_superuser": True,
            },
            "operator": {
                "password": "operator@123",
                "email": "operator@wpe.local",
                "is_staff": False,
                "is_superuser": False,
            },
        }.items():
            user, created = user_model.objects.get_or_create(
                username=username,
                defaults={
                    "email": payload["email"],
                    "is_staff": payload["is_staff"],
                    "is_superuser": payload["is_superuser"],
                    "is_active": True,
                },
            )
            needs_save = created
            for field_name in ("email", "is_staff", "is_superuser"):
                if getattr(user, field_name) != payload[field_name]:
                    setattr(user, field_name, payload[field_name])
                    needs_save = True
            if not user.is_active:
                user.is_active = True
                needs_save = True
            if created or not user.check_password(payload["password"]):
                user.set_password(payload["password"])
                needs_save = True
            if needs_save:
                user.save()
            users[username] = user
        return users

    def _seed_departments(self):
        departments = {}
        for name in ["Administration", "Sales", "Stores", "Quality", "Production", "Blending"]:
            department, _ = Department.objects.update_or_create(
                name=name,
                defaults={"is_active": True},
            )
            departments[name] = department
        return departments

    def _seed_admin_master(self):
        admin_role, _ = first_or_create(Role, {"name": "Administrator"})
        store_role, _ = first_or_create(Role, {"name": "Store Manager"})
        operator_role, _ = first_or_create(Role, {"name": "Production Operator"})

        wpe_admin_role, _ = RoleMaster.objects.update_or_create(
            name="Administrator",
            defaults={"is_active": True},
        )
        wpe_operator_role, _ = RoleMaster.objects.update_or_create(
            name="Operator",
            defaults={"is_active": True},
        )
        wpe_admin_department, _ = DepartmentMaster.objects.update_or_create(
            name="Administration",
            defaults={"is_active": True},
        )
        wpe_production_department, _ = DepartmentMaster.objects.update_or_create(
            name="Production",
            defaults={"is_active": True},
        )

        ticket_admin, _ = first_or_create(TicketUserType, {"name": "Internal Admin"})
        ticket_operator, _ = first_or_create(TicketUserType, {"name": "Plant Operator"})

        full_access_type = (
            UserType.objects.filter(department=wpe_admin_department, role=wpe_admin_role).first()
            or UserType.objects.filter(name__in=["Full Access", "Administration - Administrator"]).first()
        )
        if full_access_type is None:
            full_access_type = UserType.objects.create(
                department=wpe_admin_department,
                role=wpe_admin_role,
                is_active=True,
            )
        else:
            full_access_type.department = wpe_admin_department
            full_access_type.role = wpe_admin_role
            full_access_type.is_active = True
            full_access_type.save()

        production_type = (
            UserType.objects.filter(department=wpe_production_department, role=wpe_operator_role).first()
            or UserType.objects.filter(name__in=["Production User", "Production - Operator"]).first()
        )
        if production_type is None:
            production_type = UserType.objects.create(
                department=wpe_production_department,
                role=wpe_operator_role,
                is_active=True,
            )
        else:
            production_type.department = wpe_production_department
            production_type.role = wpe_operator_role
            production_type.is_active = True
            production_type.save()

        staff_admin, _ = Staff.objects.update_or_create(
            staff_code="9001",
            defaults={
                "name": "Admin User",
                "mobile": "9876543210",
                "email": "admin@gmail.com",
                "department": self.departments["Administration"],
                "designation": "ERP Administrator",
                "is_active": True,
            },
        )
        staff_operator, _ = Staff.objects.update_or_create(
            staff_code="9002",
            defaults={
                "name": "Plant Operator",
                "mobile": "9876543211",
                "email": "operator@wpe.local",
                "department": self.departments["Production"],
                "designation": "Production Operator",
                "is_active": True,
            },
        )

        UserCreation.objects.update_or_create(
            user=self.users[ADMIN_USERNAME],
            defaults={
                "role": admin_role,
                "staff": staff_admin,
                "ticket_user_type": ticket_admin,
                "user_type": full_access_type,
                "department": self.departments["Administration"],
                "account_status": UserCreation.AccountStatus.ACTIVE,
                "is_team_head": True,
            },
        )
        UserCreation.objects.update_or_create(
            user=self.users["operator"],
            defaults={
                "role": operator_role,
                "staff": staff_operator,
                "ticket_user_type": ticket_operator,
                "user_type": production_type,
                "department": self.departments["Production"],
                "account_status": UserCreation.AccountStatus.ACTIVE,
            },
        )

        screens = self._seed_navigation()
        full_permissions = {key: True for key in default_action_permissions()}
        view_permissions = {
            **default_action_permissions(),
            "list": True,
            "view": True,
            "print": True,
        }
        for user_type, permission_map in (
            (full_access_type, full_permissions),
            (production_type, view_permissions),
        ):
            for screen in UserScreen.objects.select_related("main_screen", "screen_section").all():
                UserTypePermission.objects.update_or_create(
                    permission_key=f"{user_type.id}:screen:{screen.id}",
                    defaults={
                        "user_type": user_type,
                        "main_screen": screen.main_screen,
                        "screen_section": screen.screen_section,
                        "user_screen": screen,
                        "scope_type": UserTypePermission.ScopeType.SCREEN,
                        "action_permissions": permission_map,
                        "status": True,
                    },
                )

        return {
            "roles": {
                "admin": admin_role,
                "store": store_role,
                "operator": operator_role,
            },
            "user_types": {
                "full": full_access_type,
                "production": production_type,
            },
            "staff": {
                "admin": staff_admin,
                "operator": staff_operator,
            },
            "screens": screens,
        }

    def _seed_navigation(self):
        nav = {
            "Masters": {
                "order": 1,
                "sections": {
                    "Admin Master": [
                        "Main Screen Master",
                        "Screen Section Master",
                        "User Screen Master",
                        "User Creation Master",
                        "User Screen Permission Master",
                    ],
                    "Common Master": ["Customer Master", "Supplier Master", "Company Master", "Project Master"],
                },
            },
            "Sales": {
                "order": 2,
                "sections": {
                    "CRM": ["Contacts", "Presales Request"],
                },
            },
            "Inventory": {
                "order": 3,
                "sections": {
                    "Store": ["Item Master", "Store Stock", "Request Approval's"],
                    "Blending": ["Blending Stock"],
                    "GRN/QCR": ["GRN", "QCR"],
                },
            },
            "Production": {
                "order": 4,
                "sections": {
                    "Production": ["Production Order", "Machine Master", "BOM Variant", "Batch Weight Entry", "Regrind Entry"],
                },
            },
        }
        screens: dict[str, UserScreen] = {}
        for main_name, main_payload in nav.items():
            main_screen, _ = MainScreen.objects.update_or_create(
                name=main_name,
                defaults={
                    "code": main_name.lower().replace("/", "-").replace(" ", "-"),
                    "order_no": main_payload["order"],
                    "status": True,
                },
            )
            for section_index, (section_name, screen_names) in enumerate(main_payload["sections"].items(), start=1):
                section, _ = ScreenSection.objects.update_or_create(
                    main_screen=main_screen,
                    name=section_name,
                    defaults={
                        "code": f"{main_screen.code}-{section_name.lower().replace('/', '-').replace(' ', '-')}",
                        "order_no": section_index,
                        "is_active": True,
                    },
                )
                for screen_index, screen_name in enumerate(screen_names, start=1):
                    code = screen_name.lower().replace("/", "-").replace(" ", "-")
                    screen, _ = UserScreen.objects.update_or_create(
                        code=code,
                        defaults={
                            "main_screen": main_screen,
                            "screen_section": section,
                            "screen_name": screen_name,
                            "folder_name": code,
                            "order_no": screen_index,
                            "icon": "Circle",
                            "is_active": True,
                            "available_actions": ["add", "update", "list", "delete", "view", "print"],
                        },
                    )
                    screens[screen_name] = screen
        return screens

    def _seed_wpe_masters(self):
        records = {
            "location": LocationMaster.objects.update_or_create(name="Coimbatore Plant", defaults={"is_active": True})[0],
            "branch": BranchMaster.objects.update_or_create(name="CBE Main Branch", defaults={"is_active": True})[0],
            "price_book": PriceBookMaster.objects.update_or_create(name="Standard INR", defaults={"is_active": True})[0],
            "warehouse": WarehouseMaster.objects.update_or_create(name="Main Store", defaults={"is_active": True})[0],
            "production_type": ProductionTypeMaster.objects.update_or_create(
                name="Recycling Production - WPE",
                defaults={"is_active": True},
            )[0],
            "sale_type": SaleTypeMaster.objects.update_or_create(name="Project Sale", defaults={"is_active": True})[0],
            "purchase_type": PurchaseTypeMaster.objects.update_or_create(name="Raw Material Purchase", defaults={"is_active": True})[0],
            "role_admin": RoleMaster.objects.update_or_create(name="Administrator", defaults={"is_active": True})[0],
            "role_operator": RoleMaster.objects.update_or_create(name="Operator", defaults={"is_active": True})[0],
            "department": DepartmentMaster.objects.update_or_create(name="Production", defaults={"is_active": True})[0],
        }

        for username, role in ((ADMIN_USERNAME, records["role_admin"]), ("operator", records["role_operator"])):
            profile, _ = WPEUserCreation.objects.update_or_create(
                user=self.users[username],
                defaults={
                    "full_name": "Admin User" if username == ADMIN_USERNAME else "Plant Operator",
                    "job_title": "ERP Administrator" if username == ADMIN_USERNAME else "Production Operator",
                    "email": self.users[username].email,
                    "phone_no": "9876543210" if username == ADMIN_USERNAME else "9876543211",
                    "location": records["location"],
                    "default_branch": records["branch"],
                    "role": role,
                    "is_active": True,
                },
            )
            profile.authorized_branches.set([records["branch"]])
            profile.authorized_price_books.set([records["price_book"]])
            profile.authorized_warehouses.set([records["warehouse"]])
            profile.authorized_production_types.set([records["production_type"]])
            profile.authorized_sale_types.set([records["sale_type"]])
            profile.authorized_purchase_types.set([records["purchase_type"]])

        for main_screen in MainScreen.objects.all():
            WPERolePermission.objects.update_or_create(
                role=records["role_admin"],
                main_screen=main_screen,
                defaults={
                    "view_all": True,
                    "view_self": True,
                    "can_add": True,
                    "can_edit": True,
                    "can_duplicate": True,
                    "can_delete": True,
                    "generate_invoice_access": True,
                    "invoice_access": True,
                    "access": True,
                },
            )

        for user_screen in UserScreen.objects.all():
            WPEUserScreenPermission.objects.update_or_create(
                user_screen=user_screen,
                defaults={
                    "view_all": True,
                    "view_self": True,
                    "can_add": True,
                    "can_edit": True,
                    "can_duplicate": True,
                    "can_delete": True,
                    "generate_invoice_access": True,
                    "invoice_access": True,
                    "access": True,
                },
            )

        return records

    def _seed_common_master(self):
        asia, _ = Continent.objects.update_or_create(
            name="Asia",
            defaults={"code": "ASIA", "order_no": 1, "status": True},
        )
        india, _ = Country.objects.update_or_create(
            code="IN",
            defaults={"continent": asia, "name": "India", "status": True},
        )
        tamil_nadu, _ = State.objects.update_or_create(
            country=india,
            name="Tamil Nadu",
            defaults={"is_active": True},
        )
        maharashtra, _ = State.objects.update_or_create(
            country=india,
            name="Maharashtra",
            defaults={"is_active": True},
        )
        karnataka, _ = State.objects.update_or_create(
            country=india,
            name="Karnataka",
            defaults={"is_active": True},
        )

        city_type, _ = CommonMaster.objects.update_or_create(
            type="CITY_TYPE",
            name="Metro",
            defaults={"is_active": True},
        )
        application_type, _ = CommonMaster.objects.update_or_create(
            type="APPLICATION_TYPE",
            name="Decking",
            defaults={"is_active": True},
        )
        CommonMaster.objects.update_or_create(type="MATERIAL_CATEGORY", name="Raw Material", defaults={"is_active": True})
        CommonMaster.objects.update_or_create(type="MATERIAL_CATEGORY", name="Finished Goods", defaults={"is_active": True})

        coimbatore, _ = City.objects.update_or_create(
            state=tamil_nadu,
            name="Coimbatore",
            defaults={
                "country": india,
                "pincode": "641001",
                "city_type": city_type,
                "is_active": True,
            },
        )
        pune, _ = City.objects.update_or_create(
            state=maharashtra,
            name="Pune",
            defaults={
                "country": india,
                "pincode": "411019",
                "city_type": city_type,
                "is_active": True,
            },
        )
        bengaluru, _ = City.objects.update_or_create(
            state=karnataka,
            name="Bengaluru",
            defaults={
                "country": india,
                "pincode": "560058",
                "city_type": city_type,
                "is_active": True,
            },
        )
        tax, _ = Tax.objects.update_or_create(
            country=india,
            name="GST 18",
            defaults={"value": money("18.00"), "is_active": True},
        )
        currency, _ = Currency.objects.update_or_create(
            country=india,
            code="INR",
            defaults={"name": "Indian Rupee", "symbol": "Rs", "is_active": True},
        )
        company, _ = Company.objects.update_or_create(
            code="WPE-CBE",
            defaults={
                "name": "WPE Demo Industries",
                "country": india,
                "state": tamil_nadu,
                "city": coimbatore,
                "pincode": "641001",
                "latitude": money("11.0168440"),
                "longitude": money("76.9558330"),
                "is_active": True,
            },
        )
        project, _ = Project.objects.update_or_create(
            code="PRJ-METRO-DECK",
            defaults={
                "company": company,
                "name": "Metro Decking Pilot",
                "client_name": "Aarav Buildtech Pvt Ltd",
                "application_type": application_type,
                "capacity": "25 MT",
                "duration": "6 Months",
                "project_date": timezone.localdate(),
                "country": india,
                "state": maharashtra,
                "city": pune,
                "address": "MIDC Industrial Area, Pune",
                "pincode": "411019",
                "pan_number": "ABCDE1234F",
                "gst_number": "27ABCDE1234F1Z5",
                "contact_person": "Rohit Mehta",
                "contact_number": "9876543212",
                "contact_email": "rohit@aaravbuildtech.in",
                "website": "https://example.com",
                "description": "Demo WPC decking project.",
                "is_active": True,
            },
        )
        return {
            "country": india,
            "states": {
                "tn": tamil_nadu,
                "mh": maharashtra,
                "ka": karnataka,
            },
            "cities": {
                "coimbatore": coimbatore,
                "pune": pune,
                "bengaluru": bengaluru,
            },
            "tax": tax,
            "currency": currency,
            "company": company,
            "project": project,
        }

    def _seed_parties(self):
        customer, _ = Customer.objects.update_or_create(
            customer_name="Aarav Buildtech Pvt Ltd",
            country=self.common["country"],
            defaults={
                "customer_group": Customer.CustomerGroup.DOMESTIC,
                "customer_division": "Projects",
                "currency": self.common["currency"],
                "state": self.common["states"]["mh"],
                "city": self.common["cities"]["pune"],
                "address": "Plot 12, MIDC Industrial Area, Pune",
                "pincode": "411019",
                "mobile_no": "9876543212",
                "phone_no": "02025551234",
                "email": "procurement@aaravbuildtech.in",
                "pan_number": "ABCDE1234F",
                "gst_number": "27ABCDE1234F1Z5",
                "gst_registered": True,
                "customer_status": Customer.CustomerStatus.ACTIVE,
                "website": "https://example.com",
                "remarks": "Demo project customer.",
                "credit_limit": money("2500000.00"),
                "payment_terms": "30 days",
                "customer_since": date(2024, 4, 1),
            },
        )
        CustomerContactPerson.objects.update_or_create(
            customer=customer,
            contact_person_name="Rohit Mehta",
            defaults={
                "designation": "Procurement Manager",
                "email": "rohit@aaravbuildtech.in",
                "mobile_no": "9876543212",
                "is_active": True,
            },
        )
        CustomerStatutoryDetail.objects.update_or_create(
            customer=customer,
            defaults={
                "cin_no": "U25209PN2020PTC000001",
                "tan_no": "PNEA12345B",
                "iec_code": "IECDEMO001",
                "is_active": True,
            },
        )
        CustomerBankDetail.objects.update_or_create(
            customer=customer,
            account_number="50100012345678",
            defaults={
                "bank_name": "HDFC Bank",
                "bank_address": "Pune Main Branch",
                "ifsc_code": "HDFC0001234",
                "beneficiary_account_name": "Aarav Buildtech Pvt Ltd",
                "is_primary": True,
                "is_active": True,
            },
        )
        CustomerAddress.objects.update_or_create(
            customer=customer,
            address_type=CustomerAddress.AddressType.BILLING,
            defaults={
                "name": "Aarav Billing Office",
                "contact_name": "Rohit Mehta",
                "contact_no": "9876543212",
                "gst_number": "27ABCDE1234F1Z5",
                "gst_status": CustomerAddress.GSTStatus.REGISTERED,
                "country": self.common["country"],
                "state": self.common["states"]["mh"],
                "city": self.common["cities"]["pune"],
                "address": "Plot 12, MIDC Industrial Area, Pune",
                "pincode": "411019",
                "is_active": True,
            },
        )
        CustomerAddress.objects.update_or_create(
            customer=customer,
            address_type=CustomerAddress.AddressType.SHIPPING,
            defaults={
                "name": "Aarav Pune Project Site",
                "contact_name": "Site Stores",
                "contact_no": "9876543213",
                "gst_number": "27ABCDE1234F1Z5",
                "gst_status": CustomerAddress.GSTStatus.REGISTERED,
                "country": self.common["country"],
                "state": self.common["states"]["mh"],
                "city": self.common["cities"]["pune"],
                "address": "Metro Decking Site, Pune",
                "pincode": "411019",
                "is_active": True,
            },
        )
        self._ensure_customer_document(customer)

        supplier, _ = Supplier.objects.update_or_create(
            supplier_name="Greenline Polymers Pvt Ltd",
            country=self.common["country"],
            defaults={
                "supplier_group": "Raw Material",
                "currency": self.common["currency"],
                "reference": "Seed Supplier",
                "corporate_address": "SIDCO Industrial Estate, Coimbatore",
                "state": self.common["states"]["tn"],
                "city": self.common["cities"]["coimbatore"],
                "address": "SIDCO Industrial Estate, Coimbatore",
                "pincode": "641021",
                "mobile_no": "9876543220",
                "phone_no": "04222555111",
                "pan_number": "PQRST1234L",
                "gst_number": "33PQRST1234L1Z6",
                "gst_status": Supplier.GSTStatus.REGISTERED,
                "email": "sales@greenlinepolymers.in",
                "website": "https://example.com",
                "msme_type": Supplier.MSMEType.SMALL,
                "payment_terms": "45 days",
                "credit_days": 45,
                "vendor_rating": money("4.50"),
                "remarks": "Demo raw material supplier.",
            },
        )
        SupplierContactPerson.objects.update_or_create(
            supplier=supplier,
            contact_person_name="Arun Sharma",
            defaults={
                "designation": "Sales Manager",
                "email": "arun@greenlinepolymers.in",
                "mobile_no": "9876543220",
                "landline": "04222555111",
                "department": "Sales",
                "is_active": True,
            },
        )
        SupplierStatutoryDetail.objects.update_or_create(
            supplier=supplier,
            defaults={
                "cin_no": "U24110TZ2019PTC000002",
                "tan_no": "CBEG12345C",
                "iec_code": "IECDEMO002",
                "is_active": True,
            },
        )
        SupplierBankDetail.objects.update_or_create(
            supplier=supplier,
            account_number="50200012345678",
            defaults={
                "bank_name": "HDFC Bank",
                "account_holder_name": "Greenline Polymers Pvt Ltd",
                "bank_address": "Coimbatore Main Branch",
                "ifsc_code": "HDFC0005678",
                "swift_code": "HDFCINBBXXX",
                "is_primary": True,
                "is_active": True,
            },
        )
        SupplierAddress.objects.update_or_create(
            supplier=supplier,
            address_type=SupplierAddress.AddressType.BILLING,
            defaults={
                "name": "Greenline Billing Office",
                "contact_name": "Arun Sharma",
                "contact_no": "9876543220",
                "gst_number": "33PQRST1234L1Z6",
                "gst_status": SupplierAddress.GSTStatus.REGISTERED,
                "country": self.common["country"],
                "state": self.common["states"]["tn"],
                "city": self.common["cities"]["coimbatore"],
                "address": "SIDCO Industrial Estate, Coimbatore",
                "pincode": "641021",
                "is_active": True,
            },
        )
        SupplierAddress.objects.update_or_create(
            supplier=supplier,
            address_type=SupplierAddress.AddressType.SHIPPING,
            defaults={
                "name": "Greenline Dispatch Warehouse",
                "contact_name": "Dispatch Team",
                "contact_no": "9876543221",
                "gst_number": "33PQRST1234L1Z6",
                "gst_status": SupplierAddress.GSTStatus.REGISTERED,
                "country": self.common["country"],
                "state": self.common["states"]["tn"],
                "city": self.common["cities"]["coimbatore"],
                "address": "Warehouse 4, SIDCO Industrial Estate, Coimbatore",
                "pincode": "641021",
                "is_active": True,
            },
        )
        self._ensure_supplier_document(supplier)

        UserCreation.objects.filter(user=self.users[ADMIN_USERNAME]).update(company=self.common["company"])
        UserCreation.objects.filter(user=self.users["operator"]).update(company=self.common["company"])
        return {"customer": customer, "supplier": supplier}

    def _ensure_customer_document(self, customer):
        if CustomerDocument.objects.filter(customer=customer, document_type="GST Certificate").exists():
            return
        document = CustomerDocument(customer=customer, document_type="GST Certificate", remarks="Seed GST document")
        document.file.save(
            "customer-gst-certificate.pdf",
            ContentFile(b"%PDF-1.4\n% WPE demo customer GST certificate\n"),
            save=True,
        )

    def _ensure_supplier_document(self, supplier):
        if SupplierDocument.objects.filter(supplier=supplier, document_type="GST Certificate").exists():
            return
        document = SupplierDocument(supplier=supplier, document_type="GST Certificate", remarks="Seed GST document")
        document.file.save(
            "supplier-gst-certificate.pdf",
            ContentFile(b"%PDF-1.4\n% WPE demo supplier GST certificate\n"),
            save=True,
        )

    def _seed_items(self):
        item_payloads = [
            {
                "external_item_id": "SEED-HDPE-001",
                "product_type": Item.PRODUCT_TYPE_GENERAL,
                "category": "Raw Material",
                "group": "Polymer",
                "sub_group": "HDPE",
                "item_name": "HDPE Natural Granules",
                "hsn_code": "39012000",
                "unit": "KG",
                "opening_stock": money("1250.000"),
                "product_details": "Primary polymer feedstock.",
            },
            {
                "external_item_id": "SEED-WOOD-001",
                "product_type": Item.PRODUCT_TYPE_GENERAL,
                "category": "Raw Material",
                "group": "Wood Flour",
                "sub_group": "80 Mesh",
                "item_name": "Wood Flour 80 Mesh",
                "hsn_code": "44050010",
                "unit": "KG",
                "opening_stock": money("980.000"),
                "product_details": "Fine mesh wood flour.",
            },
            {
                "external_item_id": "SEED-ADD-001",
                "product_type": Item.PRODUCT_TYPE_GENERAL,
                "category": "Raw Material",
                "group": "Additives",
                "sub_group": "Coupling Agent",
                "item_name": "Coupling Agent WPE-C",
                "hsn_code": "38123990",
                "unit": "KG",
                "opening_stock": money("320.000"),
                "product_details": "Coupling additive for WPC blend.",
            },
            {
                "external_item_id": "SEED-MB-001",
                "product_type": Item.PRODUCT_TYPE_GENERAL,
                "category": "Raw Material",
                "group": "Masterbatch",
                "sub_group": "Black",
                "item_name": "Black Masterbatch MB-400",
                "hsn_code": "32064990",
                "unit": "KG",
                "opening_stock": money("180.000"),
                "product_details": "Color masterbatch.",
            },
            {
                "external_item_id": "SEED-FG-001",
                "product_type": Item.PRODUCT_TYPE_PROFILE,
                "category": "Finished Goods",
                "group": "Decking",
                "sub_group": "Premium",
                "item_name": "WPC Deck Board 146x24",
                "hsn_code": "39189090",
                "unit": "NOS",
                "opening_stock": money("240.000"),
                "product_details": "Finished WPC deck board.",
            },
            {
                "external_item_id": "SEED-SCRAP-001",
                "product_type": Item.PRODUCT_TYPE_SCRAP,
                "category": "Scrap",
                "group": "Regrind",
                "sub_group": "WPC",
                "item_name": "WPC Regrind Scrap",
                "hsn_code": "39159090",
                "unit": "KG",
                "opening_stock": money("120.000"),
                "product_details": "Reusable production regrind.",
            },
        ]
        items = {}
        store_warehouse = get_store_warehouse()
        for payload in item_payloads:
            opening_stock = payload.pop("opening_stock")
            item, created = Item.objects.update_or_create(
                external_item_id=payload["external_item_id"],
                defaults={
                    **payload,
                    "opening_stock": opening_stock,
                    "current_stock": opening_stock,
                    "description": "Seed demo item.",
                    "min_max_status": True,
                    "status": True,
                },
            )
            items[payload["external_item_id"]] = item
            reference_id = f"OPEN-{payload['external_item_id']}"
            if not StoreTransaction.objects.filter(reference_id=reference_id).exists():
                apply_inward_stock(
                    item=item,
                    warehouse=store_warehouse,
                    quantity=opening_stock,
                    transaction_type=StoreTransaction.TransactionType.OPENING_STOCK,
                    reference_type=StoreTransaction.ReferenceType.OPENING_STOCK,
                    reference_id=reference_id,
                    remarks="Seed opening stock.",
                    created_by=self.users[ADMIN_USERNAME],
                    transaction_date=timezone.localdate(),
                )
            if created or not ItemStockTransaction.objects.filter(item=item, ref_id=reference_id).exists():
                ItemStockTransaction.objects.get_or_create(
                    item=item,
                    ref_id=reference_id,
                    defaults={
                        "date": timezone.localdate(),
                        "trans_type": "Opening Stock",
                        "doc_id": reference_id,
                        "contact": "System Seed",
                        "warehouse": store_warehouse.code,
                        "bin": "A1",
                        "inwards": opening_stock,
                        "outwards": money("0.000"),
                        "balance": opening_stock,
                    },
                )
        return items

    def _seed_inventory(self):
        store_warehouse = get_store_warehouse()
        blending_warehouse = get_blending_warehouse()
        qc_warehouse, _ = Warehouse.objects.update_or_create(
            code="QC_PENDING",
            defaults={
                "name": "QC Pending Warehouse - CBE",
                "warehouse_type": Warehouse.WarehouseType.QC_PENDING,
                "is_active": True,
                "is_system": True,
            },
        )
        rejected_warehouse, _ = Warehouse.objects.update_or_create(
            code="REJECTED_CBE",
            defaults={
                "name": "Rejected Warehouse - CBE",
                "warehouse_type": Warehouse.WarehouseType.REJECTED,
                "is_active": True,
                "is_system": True,
            },
        )
        _ = qc_warehouse, rejected_warehouse

        hdpe = self.items["SEED-HDPE-001"]
        wood = self.items["SEED-WOOD-001"]
        additive = self.items["SEED-ADD-001"]
        deck_board = self.items["SEED-FG-001"]

        StoreInward.objects.get_or_create(
            reference_number="LEG-IN-HDPE-001",
            defaults={
                "item": hdpe,
                "quantity": money("120.000"),
                "unit": hdpe.unit,
                "date": timezone.localdate(),
                "remarks": "Legacy inward entry seeded for UI testing.",
            },
        )
        StoreOutward.objects.get_or_create(
            reference_number="LEG-OUT-DECK-001",
            defaults={
                "item": deck_board,
                "quantity": money("18.000"),
                "unit": deck_board.unit,
                "date": timezone.localdate(),
                "remarks": "Legacy outward entry seeded for UI testing.",
            },
        )
        if not StoreTransaction.objects.filter(reference_id="IN-HDPE-SEED-001").exists():
            apply_inward_stock(
                item=hdpe,
                warehouse=store_warehouse,
                quantity=money("120.000"),
                transaction_type=StoreTransaction.TransactionType.MANUAL_INWARD,
                reference_type=StoreTransaction.ReferenceType.MANUAL,
                reference_id="IN-HDPE-SEED-001",
                remarks="Seed supplier receipt.",
                metadata={"supplier": self.parties["supplier"].supplier_name},
                created_by=self.users[ADMIN_USERNAME],
                transaction_date=timezone.localdate(),
            )
        if not StoreTransaction.objects.filter(reference_id="OUT-DECK-SEED-001").exists():
            apply_outward_stock(
                item=deck_board,
                warehouse=store_warehouse,
                quantity=money("18.000"),
                transaction_type=StoreTransaction.TransactionType.MANUAL_OUTWARD,
                reference_type=StoreTransaction.ReferenceType.MANUAL,
                reference_id="OUT-DECK-SEED-001",
                remarks="Seed customer issue.",
                metadata={"customer": self.parties["customer"].customer_name},
                created_by=self.users[ADMIN_USERNAME],
                transaction_date=timezone.localdate(),
            )
        if not StoreTransaction.objects.filter(reference_id="TRF-WOOD-SEED-001").exists():
            transfer_stock(
                item=wood,
                quantity=money("150.000"),
                source_warehouse=store_warehouse,
                destination_warehouse=blending_warehouse,
                reference_type=StoreTransaction.ReferenceType.ADJUSTMENT,
                reference_id="TRF-WOOD-SEED-001",
                remarks="Seed transfer to blending.",
                created_by=self.users[ADMIN_USERNAME],
                transaction_date=timezone.localdate(),
            )

        BlendingStock.objects.update_or_create(item=wood, defaults={"quantity": money("150.000")})
        BlendingStock.objects.update_or_create(item=additive, defaults={"quantity": money("45.000")})
        BlendingInward.objects.get_or_create(
            reference_number="BL-IN-WOOD-001",
            defaults={
                "item": wood,
                "quantity": money("150.000"),
                "unit": wood.unit,
                "date": timezone.localdate(),
                "remarks": "Seed blending inward.",
            },
        )
        BlendingOutward.objects.get_or_create(
            reference_number="BL-OUT-WOOD-001",
            defaults={
                "item": wood,
                "quantity": money("25.000"),
                "unit": wood.unit,
                "date": timezone.localdate(),
                "remarks": "Seed blending consumption.",
            },
        )

        pending_request, _ = StockRequest.objects.update_or_create(
            request_no="SR-SEED-0001",
            defaults={
                "status": StockRequest.Status.PENDING,
                "requesting_warehouse": blending_warehouse,
                "issuing_warehouse": store_warehouse,
                "request_type": StockRequest.RequestType.GENERAL,
                "department": "BLENDING",
                "requested_for_name": "Blend Trial A",
                "request_reason": "Seed request for material issue.",
                "remarks": "Pending demo request.",
                "requested_by": self.users["operator"],
            },
        )
        StockRequestItem.objects.update_or_create(
            stock_request=pending_request,
            item=additive,
            defaults={
                "requested_qty": money("12.000"),
                "approved_qty": money("0.000"),
                "issued_qty": money("0.000"),
                "remarks": "Coupling agent trial.",
            },
        )

        approved_request, _ = StockRequest.objects.update_or_create(
            request_no="SR-SEED-0002",
            defaults={
                "status": StockRequest.Status.APPROVED,
                "requesting_warehouse": blending_warehouse,
                "issuing_warehouse": store_warehouse,
                "request_type": StockRequest.RequestType.ADDITIVE,
                "department": "BLENDING",
                "requested_for_name": "Blend Trial B",
                "request_reason": "Approved seed request.",
                "remarks": "Approved demo request.",
                "approval_remarks": "Seed approval.",
                "requested_by": self.users["operator"],
                "action_by": self.users[ADMIN_USERNAME],
                "action_at": timezone.now(),
            },
        )
        StockRequestItem.objects.update_or_create(
            stock_request=approved_request,
            item=wood,
            defaults={
                "requested_qty": money("20.000"),
                "approved_qty": money("20.000"),
                "issued_qty": money("10.000"),
                "remarks": "Partially issued demo request.",
            },
        )

    def _seed_contacts(self):
        contacts = [
            {
                "phone": "9876543212",
                "name": "Aarav Buildtech",
                "email": "procurement@aaravbuildtech.in",
                "category": Contact.Category.CUSTOMER,
                "company_name": "Aarav Buildtech Pvt Ltd",
                "gstin": "27ABCDE1234F1Z5",
                "state": "Maharashtra",
                "address": "Plot 12, MIDC Industrial Area, Pune",
                "lead_source": "Expo",
                "market_segment": "Infrastructure",
                "is_active": True,
            },
            {
                "phone": "9876543220",
                "name": "Greenline Polymers",
                "email": "sales@greenlinepolymers.in",
                "category": Contact.Category.SUPPLIER,
                "company_name": "Greenline Polymers Pvt Ltd",
                "gstin": "33PQRST1234L1Z6",
                "state": "Tamil Nadu",
                "address": "SIDCO Industrial Estate, Coimbatore",
                "lead_source": "Referral",
                "market_segment": "Raw Materials",
                "is_active": True,
            },
        ]
        for payload in contacts:
            Contact.objects.update_or_create(phone=payload["phone"], defaults=payload)

    def _seed_presales(self):
        PreSales.objects.update_or_create(
            order_code="PS-DEMO-0001",
            defaults={
                "stage": "Proposal",
                "sale_type": "Project",
                "sale_category": "Primary",
                "project_name": "Metro Decking Package",
                "version_no": "V1",
                "description": "Seed presales enquiry for decking package.",
                "lead_source": "Expo",
                "sale_contact": "Aarav Buildtech",
                "gp_percent": money("18.50"),
                "gp_value": money("185000.00"),
                "line_of_business": "Decking",
                "sub_segment": "Infrastructure",
                "segment_keyword": "premium",
                "required_date": timezone.localdate() + timedelta(days=30),
                "request_person_id": 9001,
                "request_department": "Sales",
                "required_time_start": time(10, 0),
                "required_time_end": time(18, 0),
                "required_reason": "Budgetary estimate.",
                "internal_ref_id": 5001,
                "invoice_ref_id": 9001,
                "tolerance": "2%",
                "profile_type": "Deck Board",
                "capex": "No",
                "tl_code": "TL-01",
                "delivery_challan_type": "Standard",
                "indent_number": "IND-DEMO-001",
                "indent_date": aware(-3, 10, 30),
                "indent_receiving_datetime": aware(-3, 11, 0),
                "movement_description": "Seed movement description.",
                "customer_po": "PO-DEMO-1001",
                "customer_po_date": timezone.localdate(),
                "destination": "Pune Site",
                "document_contact": "Aarav Procurement Team",
                "previous_document_contact": "Legacy Contact",
                "base_order_id": 301,
                "base_customer_id": self.parties["customer"].id,
                "base_customer_name": self.parties["customer"].customer_name,
                "base_order_date": aware(-5, 9, 30),
                "activity_id": 701,
            },
        )

        request, _ = PresalesRequest.objects.update_or_create(
            request_no="PSR-SEED-0001",
            defaults={
                "request_date": timezone.localdate(),
                "category": PresalesRequest.Category.STORE,
                "request_person": "Admin User",
                "department": "Sales",
                "required_reason": "Seed store availability check.",
                "customer_type": "ADDITIVE_MO",
                "customer_name": self.parties["customer"].customer_name,
                "remarks": "Seed presales request.",
                "status": PresalesRequest.Status.APPROVED,
                "submitted_by": self.users[ADMIN_USERNAME],
                "submitted_at": timezone.now(),
                "approved_by": self.users[ADMIN_USERNAME],
                "approved_at": timezone.now(),
                "approval_remarks": "Approved by seed command.",
                "created_by": self.users[ADMIN_USERNAME],
            },
        )
        for item in [self.items["SEED-FG-001"], self.items["SEED-HDPE-001"]]:
            PresalesRequestItem.objects.update_or_create(
                presales_request=request,
                item=item,
                defaults={
                    "quantity": money("25.000") if item.unit == "NOS" else money("100.000"),
                    "unit": item.unit,
                    "remarks": "Seed request line.",
                },
            )
        if not PresalesAuditLog.objects.filter(presales_request=request, action="APPROVED").exists():
            PresalesAuditLog.objects.create(
                presales_request=request,
                action="APPROVED",
                performed_by=self.users[ADMIN_USERNAME],
                notes="Seed approval log.",
            )

    def _seed_production(self):
        machines = {
            "HSM-500-1": {
                "name": "HSM 500 - Unit 1",
                "machine_type": ProductionMachine.MachineType.HIGH_SPEED_MIX,
                "applicable_stages": "AD,BL",
                "location": "Blending Floor",
            },
            "GRAN-WPE-1": {
                "name": "Granulator WPE Blend",
                "machine_type": ProductionMachine.MachineType.GRANULATOR,
                "applicable_stages": "GL",
                "location": "Granulation Bay",
            },
        }
        machine_records = {}
        for code, defaults in machines.items():
            machine_records[code] = ProductionMachine.objects.update_or_create(
                machine_code=code,
                defaults={**defaults, "is_active": True, "notes": "Seed machine."},
            )[0]

        bom, _ = BOMVariant.objects.update_or_create(
            variant_code="BOM-SEED-001",
            defaults={
                "name": "Seed WPC Decking Blend",
                "product_item": self.items["SEED-FG-001"],
                "revision": "v1",
                "is_active": True,
                "access_password_hash": hashlib.sha256("9512".encode()).hexdigest(),
                "notes": "Seed BOM variant. Password: 9512",
                "created_by": self.users[ADMIN_USERNAME],
            },
        )
        component_payloads = [
            (self.items["SEED-HDPE-001"], "500.000", "490.000", "510.000", 1, False),
            (self.items["SEED-WOOD-001"], "250.000", "240.000", "260.000", 2, False),
            (self.items["SEED-ADD-001"], "100.000", "95.000", "105.000", 3, False),
            (self.items["SEED-SCRAP-001"], "150.000", "140.000", "160.000", 4, True),
        ]
        components = []
        for item, target, min_weight, max_weight, sequence, is_regrind in component_payloads:
            component, _ = BOMVariantComponent.objects.update_or_create(
                bom_variant=bom,
                item=item,
                defaults={
                    "target_weight_grams": money(target),
                    "min_weight_grams": money(min_weight),
                    "max_weight_grams": money(max_weight),
                    "sequence": sequence,
                    "is_regrind": is_regrind,
                    "unit": "g",
                },
            )
            components.append(component)

        order, _ = ProductionOrder.objects.update_or_create(
            production_id="PROD-SEED-0001",
            defaults={
                "production_type": "RECYCLING_PRODUCTION",
                "status": "IN_PROGRESS",
                "batch_number": "BATCH-SEED-0001",
                "batch_date": timezone.localdate(),
                "production_date": timezone.localdate(),
                "shift": "Shift 1 (6:00 am - 2:00 pm)",
                "plan_id": "PLAN-SEED-0001",
                "planned_quantity": money("1000.000"),
                "planned_weight": money("1000.000"),
                "line_number": "LINE-01",
                "line_name": "Recycling",
                "total_quantity": money("880.000"),
                "other_cost": money("12500.00"),
                "material_cost": money("68500.00"),
                "total_cost": money("81000.00"),
                "start_date_time": aware(0, 6, 0),
                "created_by": ADMIN_USERNAME,
                "updated_by": ADMIN_USERNAME,
            },
        )
        movement_payloads = [
            ("RAW_MATERIAL_IN", self.items["SEED-HDPE-001"], "Main Store", "Production Line 1", "500.000"),
            ("RAW_MATERIAL_IN", self.items["SEED-WOOD-001"], "Blending Floor", "Production Line 1", "250.000"),
            ("OUTPUT_TO_WAREHOUSE", self.items["SEED-FG-001"], "Production Line 1", "Main Store", "180.000"),
        ]
        for movement_type, item, source, destination, qty in movement_payloads:
            if not MaterialMovement.objects.filter(
                production_order=order,
                movement_type=movement_type,
                item_code=item.item_code,
            ).exists():
                MaterialMovement.objects.create(
                    production_order=order,
                    movement_type=movement_type,
                    item_id=str(item.id),
                    item_name=item.item_name,
                    item_code=item.item_code,
                    source_location=source,
                    destination_location=destination,
                    quantity=money(qty),
                    unit=item.unit,
                    warehouse=destination,
                    bin_number="P1",
                    status="COMPLETED",
                    movement_date=timezone.now(),
                )
        ProductionTransaction.objects.update_or_create(
            transaction_id="PTX-SEED-0001",
            defaults={
                "production_order": order,
                "transaction_type": "INWARD",
                "transaction_date": timezone.localdate(),
                "transaction_time": time(6, 30),
                "item_id": str(self.items["SEED-HDPE-001"].id),
                "item_number": self.items["SEED-HDPE-001"].item_code,
                "item_name": self.items["SEED-HDPE-001"].item_name,
                "item_code": self.items["SEED-HDPE-001"].item_code,
                "quantity_in": money("500.000"),
                "quantity_out": money("0.000"),
                "unit": "KG",
                "warehouse": "Main Store",
                "bin_location": "A1",
                "reference_id": order.production_id,
                "remarks": "Seed raw material issue.",
                "created_by": ADMIN_USERNAME,
            },
        )
        ProductionTransaction.objects.update_or_create(
            transaction_id="PTX-SEED-0002",
            defaults={
                "production_order": order,
                "transaction_type": "OUTWARD",
                "transaction_date": timezone.localdate(),
                "transaction_time": time(12, 0),
                "item_id": str(self.items["SEED-FG-001"].id),
                "item_number": self.items["SEED-FG-001"].item_code,
                "item_name": self.items["SEED-FG-001"].item_name,
                "item_code": self.items["SEED-FG-001"].item_code,
                "quantity_in": money("0.000"),
                "quantity_out": money("180.000"),
                "unit": "NOS",
                "warehouse": "Main Store",
                "bin_location": "FG1",
                "reference_id": order.production_id,
                "remarks": "Seed finished goods output.",
                "created_by": ADMIN_USERNAME,
            },
        )
        ProductionSummary.objects.update_or_create(
            production_order=order,
            defaults={
                "total_raw_material_cost": money("68500.00"),
                "total_other_cost": money("12500.00"),
                "total_production_cost": money("81000.00"),
                "total_input_quantity": money("1000.000"),
                "total_output_quantity": money("880.000"),
                "total_waste_quantity": money("120.000"),
                "yield_percentage": money("88.00"),
                "cost_per_unit": money("92.05"),
                "is_finalized": False,
            },
        )
        batch, _ = ProductionBatch.objects.update_or_create(
            batch_no="BATCH-SEED-0001",
            defaults={
                "production_order": order,
                "bom_variant": bom,
                "stage": ProductionBatch.Stage.BL,
                "machine": machine_records["HSM-500-1"],
                "status": ProductionBatch.BatchStatus.IN_PROGRESS,
                "started_at": aware(0, 6, 15),
                "operator": self.users["operator"],
                "notes": "Seed blending batch.",
            },
        )
        for component in components:
            weight_entry, _ = BatchWeightEntry.objects.update_or_create(
                batch=batch,
                bom_component=component,
                defaults={
                    "item": component.item,
                    "target_weight_grams": component.target_weight_grams,
                    "entered_weight_grams": component.target_weight_grams,
                    "source": "MANUAL",
                    "entered_by": self.users["operator"],
                },
            )
            weight_entry.validate_weight()
            weight_entry.save(update_fields=["is_valid", "validation_notes"])

        if not RegrindMaterialEntry.objects.filter(batch=batch, source_lot_no="RG-SEED-LOT-001").exists():
            RegrindMaterialEntry.objects.create(
                production_order=order,
                batch=batch,
                stage=ProductionBatch.Stage.BL,
                item=self.items["SEED-SCRAP-001"],
                quantity_grams=money("150.000"),
                source_lot_no="RG-SEED-LOT-001",
                is_valid=True,
                validation_notes="Seed regrind accepted.",
                notes="Seed regrind material entry.",
                added_by=self.users["operator"],
            )
