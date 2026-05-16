"""Seed migration: populate all WPE master tables with initial enum values."""

from django.db import migrations


LOCATION_NAMES = [
    "Zigma(CBE)",
    "QC Pending Warehouse - CBE",
    "Rejected Warehouse - CBE",
    "Stores",
    "Line 1 Work Center WIP",
    "Line 2 Work Center WIP",
    "Line 3 Work Center WIP",
    "Line 4 Work Center WIP",
    "Sanding Work Center WIP",
    "Brushing Work Center WIP",
    "Planning Work Center WIP",
    "Sanding And Brushing Work Center WIP",
    "Sanding(Emb) Work Center WIP",
    "Sanding And Brushing(Emb) Work Center WIP",
    "Blending Work Center WIP",
    "Recycling Work Center WIP",
    "Crumps Work Center WIP",
    "Masterbatch Work Center WIP",
    "Repack Work Center WIP",
    "Line Trail Work Center WIP",
    "Recyclable Scrap",
    "Scrap Yard",
    "Rejection Warehouse",
    "Trial Warehouse",
    "Blending RM WIP",
    "Granulation WIP",
    "Blend WIP",
    "Crumb Bag",
    "Line Additive Work Center WIP",
    "Granulation Work Center WIP",
    "Production WIP",
    "Recyclable Blend Scrap",
    "Recycled Chips",
    "Recycling WIP",
    "New Line Additive Work Center WIP",
    "New Blending Work Center WIP",
]

BRANCH_NAMES = [
    "ZIGMA GLOBAL ENVIRON SOLUTIONS PVT LIMITED",
]

PRICE_BOOK_NAMES = [
    "CBE WHS",
]

WAREHOUSE_NAMES = [
    "Crumps Work Center WIP",
    "Masterbatch Work Center WIP",
    "Repack Work Center WIP",
    "Line Trail Work Center WIP",
    "Recyclable Scrap",
    "Scrap Yard",
    "Rejection Warehouse",
    "Trial Warehouse",
    "Blending RM WIP",
    "Granulation WIP",
    "Blend WIP",
    "Crumb Bag",
    "Line Additive Work Center WIP",
    "Granulation Work Center WIP",
    "Production WIP",
    "Recyclable Blend Scrap",
    "Recycled Chips",
    "Recycling WIP",
    "New Line Additive Work Center WIP",
    "New Blending Work Center WIP",
    "Zigma(CBE)",
]

PRODUCTION_TYPE_NAMES = [
    "All",
    "WPE Additive Production",
    "Lumber Additive Production",
    "WPE Co-Ext. Production",
    "WPE Mono-Ext. Production",
    "Lumber Profile Production",
    "Crumps Production",
    "Filler Masterbatch Production",
    "Scanding Production",
    "Brushing Production",
    "Planning Production",
    "Scanding & Brushing Production",
    "Scanding with Embossing Production",
    "Scanding & Brushing with Embossing Production",
    "Recycling Production - WPE",
    "Recycling Production - Lumber",
    "Outward Movement Scrap",
    "Repack",
    "Trial Production",
    "WPE Blend Production",
    "Lumber Blend Production",
    "WPE Granulated Blend Production",
    "Lumber Granulated Blend Production",
]

SALE_TYPE_NAMES = [
    "RM Out Slip",
    "Delivery Challan",
    "MO",
    "RG Out Slip",
    "FG Out Slip",
    "Crumps Out",
    "Additive Out",
    "Sales Domestic",
    "Scrap Outslip",
]

PURCHASE_TYPE_NAMES = [
    "Regular Purchases",
    "WHS Material In",
    "MI",
    "Import Purchases",
    "RM In Slip",
    "Cash Purchases",
    "FG In Slip",
    "Crumps In",
    "Additive In",
    "Scrap Inslip",
    "RG InSlip",
]

ROLE_NAMES = [
    "Admin",
    "Production Shift Incharge",
    "Warehouse Incharge",
    "Quality Shift Incharge",
    "Quality Incharge",
    "Production Incharge",
    "Stores Incharge",
    "Blending Shift Incharge",
    "Blending Incharge",
    "Planning Executive",
    "Auditor",
    "Store Shift Incharge",
    "DTS",
    "Sr. Accountant",
    "Maintenance Incharge",
    "Management",
]

DEPARTMENT_NAMES = [
    "All Departments",
    "Admin",
    "Accounts",
    "Dispatch",
    "DTS",
    "Estimation",
    "HR",
    "Maintenance",
    "Planning",
    "Fabrication",
    "Production",
    "Blending",
    "Purchase",
    "Quality",
    "R&D",
    "Stores",
    "EDP",
    "ERP",
    "Warehouse",
]


def seed_masters(apps, schema_editor):
    LocationMaster = apps.get_model("wpe_masters", "LocationMaster")
    BranchMaster = apps.get_model("wpe_masters", "BranchMaster")
    PriceBookMaster = apps.get_model("wpe_masters", "PriceBookMaster")
    WarehouseMaster = apps.get_model("wpe_masters", "WarehouseMaster")
    ProductionTypeMaster = apps.get_model("wpe_masters", "ProductionTypeMaster")
    SaleTypeMaster = apps.get_model("wpe_masters", "SaleTypeMaster")
    PurchaseTypeMaster = apps.get_model("wpe_masters", "PurchaseTypeMaster")
    RoleMaster = apps.get_model("wpe_masters", "RoleMaster")
    DepartmentMaster = apps.get_model("wpe_masters", "DepartmentMaster")

    for name in LOCATION_NAMES:
        LocationMaster.objects.get_or_create(name=name)

    for name in BRANCH_NAMES:
        BranchMaster.objects.get_or_create(name=name)

    for name in PRICE_BOOK_NAMES:
        PriceBookMaster.objects.get_or_create(name=name)

    for name in WAREHOUSE_NAMES:
        WarehouseMaster.objects.get_or_create(name=name)

    for name in PRODUCTION_TYPE_NAMES:
        ProductionTypeMaster.objects.get_or_create(name=name)

    for name in SALE_TYPE_NAMES:
        SaleTypeMaster.objects.get_or_create(name=name)

    for name in PURCHASE_TYPE_NAMES:
        PurchaseTypeMaster.objects.get_or_create(name=name)

    for name in ROLE_NAMES:
        RoleMaster.objects.get_or_create(name=name)

    for name in DEPARTMENT_NAMES:
        DepartmentMaster.objects.get_or_create(name=name)


def unseed_masters(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("wpe_masters", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_masters, unseed_masters),
    ]
