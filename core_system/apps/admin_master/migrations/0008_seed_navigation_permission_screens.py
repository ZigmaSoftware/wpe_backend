from django.db import migrations


def seed_navigation_permission_screens(apps, schema_editor):
    MainScreen = apps.get_model("admin_master", "MainScreen")
    ScreenSection = apps.get_model("admin_master", "ScreenSection")
    UserScreen = apps.get_model("admin_master", "UserScreen")

    main_screens = {
        "dashboard": MainScreen.objects.get_or_create(
            code="dashboard",
            defaults={"name": "Dashboard", "order_no": 1, "status": True},
        )[0],
        "workspace": MainScreen.objects.get_or_create(
            code="workspace",
            defaults={"name": "WPE Workspace", "order_no": 2, "status": True},
        )[0],
        "masters": MainScreen.objects.get_or_create(
            code="masters",
            defaults={"name": "Masters", "order_no": 3, "status": True},
        )[0],
    }

    section_definitions = (
        ("dashboard-overview", "Overview", "dashboard", 1),
        ("inventory-workspace", "Inventory Workspace", "workspace", 1),
        ("blending-workspace", "Blending Workspace", "workspace", 2),
        ("production-workspace", "Production Workspace", "workspace", 3),
        ("store-workspace", "Store Workspace", "workspace", 4),
        ("grn-workspace", "GRN Workspace", "workspace", 5),
        ("contacts-workspace", "Contacts Workspace", "workspace", 6),
        ("regrind-workspace", "Regrind Workspace", "workspace", 7),
        ("admin-master", "Admin Master", "masters", 1),
        ("common-master", "Common Master", "masters", 2),
        ("inventory-store-master", "Inventory & Store Masters", "masters", 3),
        ("production-master", "Production Masters", "masters", 4),
        ("recipe-bom-master", "Recipe / BOM Masters", "masters", 5),
        ("device-label-master", "Device & Label Masters", "masters", 6),
    )

    sections = {}
    for code, name, main_key, order_no in section_definitions:
        sections[code] = ScreenSection.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "main_screen": main_screens[main_key],
                "order_no": order_no,
                "is_active": True,
            },
        )[0]

    all_actions = ["add", "update", "list", "delete", "view", "print"]
    screen_definitions = (
        ("dashboard-home", "Dashboard Home", "dashboard-overview", "/app/dashboard", 1, ["list", "view"]),
        ("inventory-store-inventory-workspace", "Store Inventory", "inventory-workspace", "/app/items/store-inventory", 1, all_actions),
        ("inventory-production-inventory-workspace", "Production Inventory", "inventory-workspace", "/app/items/production-inventory", 2, all_actions),
        ("blending-stock-workspace", "Blending Stock", "blending-workspace", "/app/blending/stock", 1, all_actions),
        ("blending-store-request-workspace", "Blending Store Request", "blending-workspace", "/app/blending/store-request", 2, all_actions),
        ("blending-transactions-workspace", "Blending Transactions", "blending-workspace", "/app/blending/transactions", 3, all_actions),
        ("production-ad-weightage-workspace", "AD Weightage", "production-workspace", "/app/production/ad-weightage", 1, all_actions),
        ("production-bl-blending-workspace", "BL Blending", "production-workspace", "/app/production/bl-blending", 2, all_actions),
        ("production-gl-granulation-workspace", "GL Granulation", "production-workspace", "/app/production/gl-granulation", 3, all_actions),
        ("production-pr-production-workspace", "PR Production", "production-workspace", "/app/production/pr-production", 4, all_actions),
        ("store-stock-workspace", "Store Stock", "store-workspace", "/app/store/stock", 1, all_actions),
        ("store-request-workspace", "Store Request", "store-workspace", "/app/store/request", 2, all_actions),
        ("store-transactions-workspace", "Store Transactions", "store-workspace", "/app/store/transactions", 3, all_actions),
        ("grn-process-workspace", "GRN Process", "grn-workspace", "/app/grn/process", 1, all_actions),
        ("grn-status-workspace", "GRN Status", "grn-workspace", "/app/grn/status", 2, all_actions),
        ("contacts-workspace", "Contacts", "contacts-workspace", "/app/contacts", 1, all_actions),
        ("regrind-workspace", "Regrind", "regrind-workspace", "/app/regrind", 1, all_actions),
        ("main-screen-master", "Main Screen Master", "admin-master", "/admin/main-screens", 1, all_actions),
        ("screen-section-master", "Screen Section Master", "admin-master", "/admin/screen-sections", 2, all_actions),
        ("user-screen-master", "User Screen Master", "admin-master", "/admin/user-screens", 3, all_actions),
        ("department-master", "Department Master", "admin-master", "/wpe-masters/departments", 4, all_actions),
        ("staff-creation-master", "Staff Creation", "admin-master", "/admin/staff-creation", 5, all_actions),
        ("role-master", "Role Master", "admin-master", "/wpe-masters/roles", 6, all_actions),
        ("user-type-master", "User Type / Role Mapping", "admin-master", "/admin/user-types", 7, all_actions),
        ("user-creation-master", "User Creation Master", "admin-master", "/admin/user-creation", 8, all_actions),
        ("user-screen-permission-master", "User Screen Permission Master", "admin-master", "/admin/user-screen-permission", 9, all_actions),
        ("continent-master", "Continent Master", "common-master", "/masters/continents", 1, all_actions),
        ("country-master", "Country Master", "common-master", "/masters/countries", 2, all_actions),
        ("state-master", "State Master", "common-master", "/masters/states", 3, all_actions),
        ("city-master", "City Master", "common-master", "/masters/cities", 4, all_actions),
        ("tax-master", "Tax Master", "common-master", "/masters/taxes", 5, all_actions),
        ("currency-master", "Currency Master", "common-master", "/masters/currencies", 6, all_actions),
        ("customer-master", "Customer Master", "common-master", "/masters/customers", 7, all_actions),
        ("supplier-master", "Supplier Master", "common-master", "/masters/suppliers", 8, all_actions),
        ("company-master", "Company Master", "common-master", "/masters/companies", 9, all_actions),
        ("wpe-product-type-master", "Item Category", "inventory-store-master", "/wpe-masters/product-types", 1, all_actions),
        ("wpe-product-subtype-master", "Item Sub Category", "inventory-store-master", "/wpe-masters/product-subtypes", 2, all_actions),
        ("unit-master", "Unit Master", "inventory-store-master", "/wpe-masters/units", 3, all_actions),
        ("item-creation-master", "Item Creation Master", "inventory-store-master", "/wpe-masters/item-creations", 4, all_actions),
        ("store-master", "Store Master", "inventory-store-master", "/wpe-masters/stores", 5, all_actions),
        ("warehouse-master", "Warehouse Master", "inventory-store-master", "/wpe-masters/warehouses", 6, all_actions),
        ("location-master", "Location Master", "inventory-store-master", "/wpe-masters/locations", 7, all_actions),
        ("production-type-master", "Production Type Master", "inventory-store-master", "/wpe-masters/production-types", 8, all_actions),
        ("sale-type-master", "Sale Type Master", "inventory-store-master", "/wpe-masters/sale-types", 9, all_actions),
        ("purchase-type-master", "Purchase Type Master", "inventory-store-master", "/wpe-masters/purchase-types", 10, all_actions),
        ("profile-creation-master", "Profile Creation Master", "production-master", "/masters/production-masters/profile-creations", 1, all_actions),
        ("profile-size-master", "Profile Size Master", "production-master", "/masters/production-masters/profile-sizes", 2, all_actions),
        ("color-creation-master", "Color Creation Master", "production-master", "/masters/production-masters/color-creations", 3, all_actions),
        ("machine-creation-master", "Machine Creation Master", "production-master", "/masters/production-masters/machine-creations", 4, all_actions),
        ("work-centre-creation-master", "Work Centre Creation Master", "production-master", "/masters/production-masters/work-centre-creations", 5, all_actions),
        ("production-line-master", "Production Line Master", "production-master", "/masters/production-masters/production-lines", 6, all_actions),
        ("bin-creation-master", "Bin Creation Master", "production-master", "/masters/production-masters/bin-creations", 7, all_actions),
        ("bag-creation-master", "Bag Creation Master", "production-master", "/masters/production-masters/bag-creations", 8, all_actions),
        ("packing-type-master", "Packing Type Master", "production-master", "/masters/production-masters/packing-types", 9, all_actions),
        ("packing-material-master", "Packing Material Master", "production-master", "/masters/production-masters/packing-materials", 10, all_actions),
        ("recipe-creation-master", "Recipe Creation Master", "recipe-bom-master", "/masters/recipe-bom-masters/recipe-creations", 1, all_actions),
        ("recipe-item-creation-master", "Recipe Item Creation Master", "recipe-bom-master", "/masters/recipe-bom-masters/recipe-item-creations", 2, all_actions),
        ("bom-creation-master", "BOM Creation Master", "recipe-bom-master", "/masters/recipe-bom-masters/bom-creations", 3, all_actions),
        ("bom-item-creation-master", "BOM Item Creation Master", "recipe-bom-master", "/masters/recipe-bom-masters/bom-item-creations", 4, all_actions),
        ("weighment-scale-master", "Weighment Scale Master", "device-label-master", "/masters/device-label-masters/weighment-scale-creations", 1, all_actions),
        ("printer-master", "Printer Master", "device-label-master", "/masters/device-label-masters/printer-creations", 2, all_actions),
        ("qr-label-template-master", "QR Label Template Master", "device-label-master", "/masters/device-label-masters/qr-label-templates", 3, all_actions),
        ("serial-port-configuration-master", "Serial Port Configuration Master", "device-label-master", "/masters/device-label-masters/serial-port-configurations", 4, all_actions),
    )

    for code, name, section_code, folder_name, order_no, available_actions in screen_definitions:
        UserScreen.objects.get_or_create(
            code=code,
            defaults={
                "main_screen": sections[section_code].main_screen,
                "screen_section": sections[section_code],
                "screen_name": name,
                "folder_name": folder_name,
                "order_no": order_no,
                "is_active": True,
                "available_actions": available_actions,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0007_staff_department_master_staff_role_master"),
    ]

    operations = [
        migrations.RunPython(seed_navigation_permission_screens, migrations.RunPython.noop),
    ]
