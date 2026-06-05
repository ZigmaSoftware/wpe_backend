"""Development-only bootstrap data for admin master navigation."""

from __future__ import annotations

import os

from django.conf import settings
from django.contrib.auth import get_user_model

from .models import MainScreen, ScreenSection, UserScreen


def ensure_dev_full_access_user() -> None:
    if not settings.DEBUG or os.environ.get("BP_SKIP_DEV_BOOTSTRAP") == "1":
        return

    username = os.environ.get("DEV_FULL_ACCESS_USERNAME", "imran").strip()
    password = os.environ.get("DEV_FULL_ACCESS_PASSWORD", "developer")
    email = os.environ.get("DEV_FULL_ACCESS_EMAIL", "")

    if not username or not password:
        return

    user_model = get_user_model()
    user, created = user_model.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )

    needs_save = created
    if user.email != email:
        user.email = email
        needs_save = True
    if not user.is_staff:
        user.is_staff = True
        needs_save = True
    if not user.is_superuser:
        user.is_superuser = True
        needs_save = True
    if not user.is_active:
        user.is_active = True
        needs_save = True
    if created or not user.check_password(password):
        user.set_password(password)
        needs_save = True

    if needs_save:
        user.save()


def ensure_dev_master_data() -> None:
    if not settings.DEBUG or os.environ.get("BP_SKIP_DEV_BOOTSTRAP") == "1":
        return

    ensure_dev_full_access_user()

    dashboard_screen, _ = MainScreen.objects.get_or_create(
        name="Dashboard",
        defaults={"code": "dashboard", "order_no": 1, "status": True},
    )

    workspace_screen, _ = MainScreen.objects.get_or_create(
        name="WPE Workspace",
        defaults={"code": "workspace", "order_no": 2, "status": True},
    )

    masters_screen, _ = MainScreen.objects.get_or_create(
        name="Masters",
        defaults={"code": "masters", "order_no": 3, "status": True},
    )

    dashboard_section, _ = ScreenSection.objects.get_or_create(
        name="Overview",
        main_screen=dashboard_screen,
        defaults={"code": "dashboard-overview", "order_no": 1, "is_active": True},
    )

    inventory_workspace_section, _ = ScreenSection.objects.get_or_create(
        name="Inventory Workspace",
        main_screen=workspace_screen,
        defaults={"code": "inventory-workspace", "order_no": 1, "is_active": True},
    )

    blending_workspace_section, _ = ScreenSection.objects.get_or_create(
        name="Blending Workspace",
        main_screen=workspace_screen,
        defaults={"code": "blending-workspace", "order_no": 2, "is_active": True},
    )

    production_workspace_section, _ = ScreenSection.objects.get_or_create(
        name="Production Workspace",
        main_screen=workspace_screen,
        defaults={"code": "production-workspace", "order_no": 3, "is_active": True},
    )

    store_workspace_section, _ = ScreenSection.objects.get_or_create(
        name="Store Workspace",
        main_screen=workspace_screen,
        defaults={"code": "store-workspace", "order_no": 4, "is_active": True},
    )

    grn_workspace_section, _ = ScreenSection.objects.get_or_create(
        name="GRN Workspace",
        main_screen=workspace_screen,
        defaults={"code": "grn-workspace", "order_no": 5, "is_active": True},
    )

    contacts_workspace_section, _ = ScreenSection.objects.get_or_create(
        name="Contacts Workspace",
        main_screen=workspace_screen,
        defaults={"code": "contacts-workspace", "order_no": 6, "is_active": True},
    )

    regrind_workspace_section, _ = ScreenSection.objects.get_or_create(
        name="Regrind Workspace",
        main_screen=workspace_screen,
        defaults={"code": "regrind-workspace", "order_no": 7, "is_active": True},
    )

    admin_section, _ = ScreenSection.objects.get_or_create(
        name="Admin Master",
        main_screen=masters_screen,
        defaults={"code": "admin-master", "order_no": 1, "is_active": True},
    )

    common_section, _ = ScreenSection.objects.get_or_create(
        name="Common Master",
        main_screen=masters_screen,
        defaults={"code": "common-master", "order_no": 2, "is_active": True},
    )

    inventory_store_section, _ = ScreenSection.objects.get_or_create(
        name="Inventory & Store Masters",
        main_screen=masters_screen,
        defaults={"code": "inventory-store-master", "order_no": 3, "is_active": True},
    )

    production_masters_section, _ = ScreenSection.objects.get_or_create(
        name="Production Masters",
        main_screen=masters_screen,
        defaults={"code": "production-master", "order_no": 4, "is_active": True},
    )

    recipe_bom_section, _ = ScreenSection.objects.get_or_create(
        name="Recipe / BOM Masters",
        main_screen=masters_screen,
        defaults={"code": "recipe-bom-master", "order_no": 5, "is_active": True},
    )

    device_label_section, _ = ScreenSection.objects.get_or_create(
        name="Device & Label Masters",
        main_screen=masters_screen,
        defaults={"code": "device-label-master", "order_no": 6, "is_active": True},
    )

    dev_screens = (
        {
            "screen_name": "Dashboard Home",
            "code": "dashboard-home",
            "section": dashboard_section,
            "order_no": 1,
            "folder_name": "/app/dashboard",
            "available_actions": ["list", "view"],
        },
        {
            "screen_name": "Store Inventory",
            "code": "inventory-store-inventory-workspace",
            "section": inventory_workspace_section,
            "order_no": 1,
            "folder_name": "/app/items/store-inventory",
        },
        {
            "screen_name": "Production Inventory",
            "code": "inventory-production-inventory-workspace",
            "section": inventory_workspace_section,
            "order_no": 2,
            "folder_name": "/app/items/production-inventory",
        },
        {
            "screen_name": "Blending Stock",
            "code": "blending-stock-workspace",
            "section": blending_workspace_section,
            "order_no": 1,
            "folder_name": "/app/blending/stock",
        },
        {
            "screen_name": "Blending Store Request",
            "code": "blending-store-request-workspace",
            "section": blending_workspace_section,
            "order_no": 2,
            "folder_name": "/app/blending/store-request",
        },
        {
            "screen_name": "Blending Transactions",
            "code": "blending-transactions-workspace",
            "section": blending_workspace_section,
            "order_no": 3,
            "folder_name": "/app/blending/transactions",
        },
        {
            "screen_name": "AD Weightage",
            "code": "production-ad-weightage-workspace",
            "section": production_workspace_section,
            "order_no": 1,
            "folder_name": "/app/production/ad-weightage",
        },
        {
            "screen_name": "BL Blending",
            "code": "production-bl-blending-workspace",
            "section": production_workspace_section,
            "order_no": 2,
            "folder_name": "/app/production/bl-blending",
        },
        {
            "screen_name": "GL Granulation",
            "code": "production-gl-granulation-workspace",
            "section": production_workspace_section,
            "order_no": 3,
            "folder_name": "/app/production/gl-granulation",
        },
        {
            "screen_name": "PR Production",
            "code": "production-pr-production-workspace",
            "section": production_workspace_section,
            "order_no": 4,
            "folder_name": "/app/production/pr-production",
        },
        {
            "screen_name": "Store Stock",
            "code": "store-stock-workspace",
            "section": store_workspace_section,
            "order_no": 1,
            "folder_name": "/app/store/stock",
        },
        {
            "screen_name": "Request Approval's",
            "code": "store-request-workspace",
            "section": store_workspace_section,
            "order_no": 2,
            "folder_name": "/app/store/request",
        },
        {
            "screen_name": "Store Transactions",
            "code": "store-transactions-workspace",
            "section": store_workspace_section,
            "order_no": 3,
            "folder_name": "/app/store/transactions",
        },
        {
            "screen_name": "GRN Process",
            "code": "grn-process-workspace",
            "section": grn_workspace_section,
            "order_no": 1,
            "folder_name": "/app/grn/process",
        },
        {
            "screen_name": "GRN Status",
            "code": "grn-status-workspace",
            "section": grn_workspace_section,
            "order_no": 2,
            "folder_name": "/app/grn/status",
        },
        {
            "screen_name": "Contacts",
            "code": "contacts-workspace",
            "section": contacts_workspace_section,
            "order_no": 1,
            "folder_name": "/app/contacts",
        },
        {
            "screen_name": "Regrind",
            "code": "regrind-workspace",
            "section": regrind_workspace_section,
            "order_no": 1,
            "folder_name": "/app/regrind",
        },
        {
            "screen_name": "Main Screen Master",
            "code": "main-screen-master",
            "section": admin_section,
            "order_no": 1,
            "folder_name": "/admin/main-screens",
        },
        {
            "screen_name": "Screen Section Master",
            "code": "screen-section-master",
            "section": admin_section,
            "order_no": 2,
            "folder_name": "/admin/screen-sections",
        },
        {
            "screen_name": "User Screen Master",
            "code": "user-screen-master",
            "section": admin_section,
            "order_no": 3,
            "folder_name": "/admin/user-screens",
        },
        {
            "screen_name": "Department Master",
            "code": "department-master",
            "section": admin_section,
            "order_no": 4,
            "folder_name": "/wpe-masters/departments",
        },
        {
            "screen_name": "Staff Creation",
            "code": "staff-creation-master",
            "section": admin_section,
            "order_no": 5,
            "folder_name": "/admin/staff-creation",
        },
        {
            "screen_name": "Role Master",
            "code": "role-master",
            "section": admin_section,
            "order_no": 6,
            "folder_name": "/wpe-masters/roles",
        },
        {
            "screen_name": "User Type / Role Mapping",
            "code": "user-type-master",
            "section": admin_section,
            "order_no": 7,
            "folder_name": "/admin/user-types",
        },
        {
            "screen_name": "User Creation Master",
            "code": "user-creation-master",
            "section": admin_section,
            "order_no": 8,
            "folder_name": "/admin/user-creation",
        },
        {
            "screen_name": "User Screen Permission Master",
            "code": "user-screen-permission-master",
            "section": admin_section,
            "order_no": 9,
            "folder_name": "/admin/user-screen-permission",
        },
        {
            "screen_name": "Continent Master",
            "code": "continent-master",
            "section": common_section,
            "order_no": 1,
            "folder_name": "/masters/continents",
        },
        {
            "screen_name": "Country Master",
            "code": "country-master",
            "section": common_section,
            "order_no": 2,
            "folder_name": "/masters/countries",
        },
        {
            "screen_name": "State Master",
            "code": "state-master",
            "section": common_section,
            "order_no": 3,
            "folder_name": "/masters/states",
        },
        {
            "screen_name": "City Master",
            "code": "city-master",
            "section": common_section,
            "order_no": 4,
            "folder_name": "/masters/cities",
        },
        {
            "screen_name": "Tax Master",
            "code": "tax-master",
            "section": common_section,
            "order_no": 5,
            "folder_name": "/masters/taxes",
        },
        {
            "screen_name": "Currency Master",
            "code": "currency-master",
            "section": common_section,
            "order_no": 6,
            "folder_name": "/masters/currencies",
        },
        {
            "screen_name": "Customer Master",
            "code": "customer-master",
            "section": common_section,
            "order_no": 7,
            "folder_name": "/masters/customers",
        },
        {
            "screen_name": "Supplier Master",
            "code": "supplier-master",
            "section": common_section,
            "order_no": 8,
            "folder_name": "/masters/suppliers",
        },
        {
            "screen_name": "Company Master",
            "code": "company-master",
            "section": common_section,
            "order_no": 9,
            "folder_name": "/masters/companies",
        },
        {
            "screen_name": "Item Category",
            "code": "wpe-product-type-master",
            "section": inventory_store_section,
            "order_no": 1,
            "folder_name": "/wpe-masters/product-types",
        },
        {
            "screen_name": "Item Sub Category",
            "code": "wpe-product-subtype-master",
            "section": inventory_store_section,
            "order_no": 2,
            "folder_name": "/wpe-masters/product-subtypes",
        },
        {
            "screen_name": "Unit Master",
            "code": "unit-master",
            "section": inventory_store_section,
            "order_no": 3,
            "folder_name": "/wpe-masters/units",
        },
        {
            "screen_name": "Item Creation Master",
            "code": "item-creation-master",
            "section": inventory_store_section,
            "order_no": 4,
            "folder_name": "/wpe-masters/item-creations",
        },
        {
            "screen_name": "Store Master",
            "code": "store-master",
            "section": inventory_store_section,
            "order_no": 5,
            "folder_name": "/wpe-masters/stores",
        },
        {
            "screen_name": "Warehouse Master",
            "code": "warehouse-master",
            "section": inventory_store_section,
            "order_no": 6,
            "folder_name": "/wpe-masters/warehouses",
        },
        {
            "screen_name": "Location Master",
            "code": "location-master",
            "section": inventory_store_section,
            "order_no": 7,
            "folder_name": "/wpe-masters/locations",
        },
        {
            "screen_name": "Production Type Master",
            "code": "production-type-master",
            "section": inventory_store_section,
            "order_no": 8,
            "folder_name": "/wpe-masters/production-types",
        },
        {
            "screen_name": "Sale Type Master",
            "code": "sale-type-master",
            "section": inventory_store_section,
            "order_no": 9,
            "folder_name": "/wpe-masters/sale-types",
        },
        {
            "screen_name": "Purchase Type Master",
            "code": "purchase-type-master",
            "section": inventory_store_section,
            "order_no": 10,
            "folder_name": "/wpe-masters/purchase-types",
        },
        {
            "screen_name": "Profile Creation Master",
            "code": "profile-creation-master",
            "section": production_masters_section,
            "order_no": 1,
            "folder_name": "/masters/production-masters/profile-creations",
        },
        {
            "screen_name": "Profile Size Master",
            "code": "profile-size-master",
            "section": production_masters_section,
            "order_no": 2,
            "folder_name": "/masters/production-masters/profile-sizes",
        },
        {
            "screen_name": "Color Creation Master",
            "code": "color-creation-master",
            "section": production_masters_section,
            "order_no": 3,
            "folder_name": "/masters/production-masters/color-creations",
        },
        {
            "screen_name": "Machine Creation Master",
            "code": "machine-creation-master",
            "section": production_masters_section,
            "order_no": 4,
            "folder_name": "/masters/production-masters/machine-creations",
        },
        {
            "screen_name": "Work Centre Creation Master",
            "code": "work-centre-creation-master",
            "section": production_masters_section,
            "order_no": 5,
            "folder_name": "/masters/production-masters/work-centre-creations",
        },
        {
            "screen_name": "Production Line Master",
            "code": "production-line-master",
            "section": production_masters_section,
            "order_no": 6,
            "folder_name": "/masters/production-masters/production-lines",
        },
        {
            "screen_name": "Bin Creation Master",
            "code": "bin-creation-master",
            "section": production_masters_section,
            "order_no": 7,
            "folder_name": "/masters/production-masters/bin-creations",
        },
        {
            "screen_name": "Bag Creation Master",
            "code": "bag-creation-master",
            "section": production_masters_section,
            "order_no": 8,
            "folder_name": "/masters/production-masters/bag-creations",
        },
        {
            "screen_name": "Packing Type Master",
            "code": "packing-type-master",
            "section": production_masters_section,
            "order_no": 9,
            "folder_name": "/masters/production-masters/packing-types",
        },
        {
            "screen_name": "Packing Material Master",
            "code": "packing-material-master",
            "section": production_masters_section,
            "order_no": 10,
            "folder_name": "/masters/production-masters/packing-materials",
        },
        {
            "screen_name": "Recipe Creation Master",
            "code": "recipe-creation-master",
            "section": recipe_bom_section,
            "order_no": 1,
            "folder_name": "/masters/recipe-bom-masters/recipe-creations",
        },
        {
            "screen_name": "Recipe Item Creation Master",
            "code": "recipe-item-creation-master",
            "section": recipe_bom_section,
            "order_no": 2,
            "folder_name": "/masters/recipe-bom-masters/recipe-item-creations",
        },
        {
            "screen_name": "BOM Creation Master",
            "code": "bom-creation-master",
            "section": recipe_bom_section,
            "order_no": 3,
            "folder_name": "/masters/recipe-bom-masters/bom-creations",
        },
        {
            "screen_name": "BOM Item Creation Master",
            "code": "bom-item-creation-master",
            "section": recipe_bom_section,
            "order_no": 4,
            "folder_name": "/masters/recipe-bom-masters/bom-item-creations",
        },
        {
            "screen_name": "Weighment Scale Master",
            "code": "weighment-scale-master",
            "section": device_label_section,
            "order_no": 1,
            "folder_name": "/masters/device-label-masters/weighment-scale-creations",
        },
        {
            "screen_name": "Printer Master",
            "code": "printer-master",
            "section": device_label_section,
            "order_no": 2,
            "folder_name": "/masters/device-label-masters/printer-creations",
        },
        {
            "screen_name": "QR Label Template Master",
            "code": "qr-label-template-master",
            "section": device_label_section,
            "order_no": 3,
            "folder_name": "/masters/device-label-masters/qr-label-templates",
        },
        {
            "screen_name": "Serial Port Configuration Master",
            "code": "serial-port-configuration-master",
            "section": device_label_section,
            "order_no": 4,
            "folder_name": "/masters/device-label-masters/serial-port-configurations",
        },
    )

    for screen in dev_screens:
        UserScreen.objects.get_or_create(
            code=screen["code"],
            defaults={
                "main_screen": screen["section"].main_screen,
                "screen_section": screen["section"],
                "screen_name": screen["screen_name"],
                "folder_name": screen.get("folder_name", screen["code"]),
                "order_no": screen["order_no"],
                "is_active": True,
                "available_actions": screen.get(
                    "available_actions",
                    ["add", "update", "list", "delete", "view", "print"],
                ),
            },
        )
