from django.db import migrations


ALL_ACTIONS = ["add", "update", "list", "delete", "view", "print"]
DASHBOARD_ACTIONS = ["list", "view"]

REQUESTS_SECTION_CODE = "requests-workspace"
REQUESTS_SECTION_NAME = "Requests"
REQUESTS_SCREEN_CODE = "requests-store-request-workspace"
REQUESTS_SCREEN_NAME = "Store Request"
REQUESTS_SCREEN_PATH = "/app/requests/store-request"
REQUESTS_SCREEN_ALIASES = ("blending-store-request-workspace", "store-request")

OBSOLETE_SECTION_CODES = {
    "2-dashboard": None,
    "2-request": REQUESTS_SECTION_CODE,
    "wpe-masters": "inventory-store-master",
}

OBSOLETE_SCREEN_CODES = {"IND"}


def _permission_key(user_type_id, scope_type, scope_id):
    return f"{user_type_id}:{scope_type}:{scope_id}"


def _merge_action_permissions(current, incoming):
    current_map = current or {}
    incoming_map = incoming or {}
    keys = ("all", "add", "update", "list", "delete", "view", "print")
    return {key: bool(current_map.get(key) or incoming_map.get(key)) for key in keys}


def _upsert_main_screen(MainScreen, *, code, name, order_no):
    screen, _ = MainScreen.objects.get_or_create(
        code=code,
        defaults={"name": name, "order_no": order_no, "status": True},
    )
    updates = []
    if screen.name != name:
        screen.name = name
        updates.append("name")
    if screen.order_no != order_no:
        screen.order_no = order_no
        updates.append("order_no")
    if not screen.status:
        screen.status = True
        updates.append("status")
    if updates:
        screen.save(update_fields=updates)
    return screen


def _upsert_section(ScreenSection, *, main_screen, code, name, order_no):
    section, _ = ScreenSection.objects.get_or_create(
        code=code,
        defaults={
            "name": name,
            "main_screen": main_screen,
            "order_no": order_no,
            "is_active": True,
        },
    )
    updates = []
    if section.name != name:
        section.name = name
        updates.append("name")
    if section.main_screen_id != main_screen.id:
        section.main_screen = main_screen
        updates.append("main_screen")
    if section.order_no != order_no:
        section.order_no = order_no
        updates.append("order_no")
    if not section.is_active:
        section.is_active = True
        updates.append("is_active")
    if updates:
        section.save(update_fields=updates)
    return section


def _merge_permission_scope(
    UserTypePermission,
    permission,
    *,
    main_screen_id,
    screen_section_id=None,
    user_screen_id=None,
):
    scope_type = permission.scope_type
    if scope_type == "screen":
        scope_id = user_screen_id
    elif scope_type == "section":
        scope_id = screen_section_id
    else:
        scope_id = main_screen_id

    permission_key = _permission_key(permission.user_type_id, scope_type, scope_id)
    existing = (
        UserTypePermission.objects.filter(
            user_type_id=permission.user_type_id,
            scope_type=scope_type,
            permission_key=permission_key,
        )
        .exclude(pk=permission.pk)
        .first()
    )

    target_values = {
        "main_screen_id": main_screen_id,
        "screen_section_id": screen_section_id,
        "user_screen_id": user_screen_id,
        "permission_key": permission_key,
    }

    if existing:
        existing.action_permissions = _merge_action_permissions(existing.action_permissions, permission.action_permissions)
        existing.status = bool(existing.status or permission.status)
        for field, value in target_values.items():
            setattr(existing, field, value)
        existing.save(
            update_fields=[
                "main_screen",
                "screen_section",
                "user_screen",
                "permission_key",
                "action_permissions",
                "status",
            ]
        )
        permission.delete()
        return existing

    for field, value in target_values.items():
        setattr(permission, field, value)
    permission.save(
        update_fields=["main_screen", "screen_section", "user_screen", "permission_key"]
    )
    return permission


def _merge_screen_permissions(UserTypePermission, *, source_screen_ids, target_screen):
    for permission in UserTypePermission.objects.filter(user_screen_id__in=source_screen_ids).order_by("id"):
        _merge_permission_scope(
            UserTypePermission,
            permission,
            main_screen_id=target_screen.main_screen_id,
            screen_section_id=target_screen.screen_section_id,
            user_screen_id=target_screen.id,
        )


def _merge_section_permissions(UserTypePermission, *, source_section_ids, target_section):
    for permission in UserTypePermission.objects.filter(
        scope_type="section",
        screen_section_id__in=source_section_ids,
    ).order_by("id"):
        _merge_permission_scope(
            UserTypePermission,
            permission,
            main_screen_id=target_section.main_screen_id,
            screen_section_id=target_section.id,
            user_screen_id=None,
        )


def _upsert_screen(
    UserScreen,
    UserTypePermission,
    *,
    sections_by_code,
    code,
    name,
    section_code,
    folder_name,
    order_no,
    available_actions,
    aliases=(),
):
    screen = UserScreen.objects.filter(code=code).first()
    alias_screens = list(
        UserScreen.objects.filter(code__in=aliases)
        .exclude(pk=getattr(screen, "pk", None))
        .order_by("id")
    )

    if screen is None and alias_screens:
        screen = alias_screens[0]
        alias_screens = alias_screens[1:]

    section = sections_by_code[section_code]
    if screen is None:
        screen = UserScreen.objects.create(
            main_screen=section.main_screen,
            screen_section=section,
            screen_name=name,
            code=code,
            folder_name=folder_name,
            order_no=order_no,
            is_active=True,
            available_actions=available_actions,
        )
    else:
        screen.main_screen = section.main_screen
        screen.screen_section = section
        screen.screen_name = name
        screen.code = code
        screen.folder_name = folder_name
        screen.order_no = order_no
        screen.is_active = True
        screen.available_actions = available_actions
        screen.save(
            update_fields=[
                "main_screen",
                "screen_section",
                "screen_name",
                "code",
                "folder_name",
                "order_no",
                "is_active",
                "available_actions",
            ]
        )

    UserTypePermission.objects.filter(user_screen_id=screen.id).update(
        main_screen_id=screen.main_screen_id,
        screen_section_id=screen.screen_section_id,
    )

    if alias_screens:
        _merge_screen_permissions(
            UserTypePermission,
            source_screen_ids=[alias_screen.id for alias_screen in alias_screens],
            target_screen=screen,
        )
        UserScreen.objects.filter(pk__in=[alias_screen.id for alias_screen in alias_screens]).delete()

    return screen


def normalize_navigation_permission_screens(apps, schema_editor):
    MainScreen = apps.get_model("admin_master", "MainScreen")
    ScreenSection = apps.get_model("admin_master", "ScreenSection")
    UserScreen = apps.get_model("admin_master", "UserScreen")
    UserTypePermission = apps.get_model("admin_master", "UserTypePermission")

    dashboard_main = _upsert_main_screen(MainScreen, code="dashboard", name="Dashboard", order_no=1)
    workspace_main = _upsert_main_screen(MainScreen, code="workspace", name="WPE Workspace", order_no=2)
    masters_main = _upsert_main_screen(MainScreen, code="masters", name="Masters", order_no=3)

    section_definitions = (
        ("dashboard-overview", "Overview", dashboard_main, 1),
        ("inventory-workspace", "Inventory Workspace", workspace_main, 1),
        ("blending-workspace", "Blending Workspace", workspace_main, 2),
        ("production-workspace", "Production Workspace", workspace_main, 3),
        ("store-workspace", "Store Workspace", workspace_main, 4),
        ("grn-workspace", "GRN Workspace", workspace_main, 5),
        ("contacts-workspace", "Contacts Workspace", workspace_main, 6),
        ("regrind-workspace", "Regrind Workspace", workspace_main, 7),
        (REQUESTS_SECTION_CODE, REQUESTS_SECTION_NAME, workspace_main, 8),
        ("admin-master", "Admin Masters", masters_main, 1),
        ("common-master", "Common Masters", masters_main, 2),
        ("inventory-store-master", "Inventory & Store Masters", masters_main, 3),
        ("production-master", "Production Masters", masters_main, 4),
        ("recipe-bom-master", "Recipe / BOM Masters", masters_main, 5),
        ("device-label-master", "Device & Label Masters", masters_main, 6),
    )
    sections_by_code = {
        code: _upsert_section(
            ScreenSection,
            main_screen=main_screen,
            code=code,
            name=name,
            order_no=order_no,
        )
        for code, name, main_screen, order_no in section_definitions
    }

    screen_definitions = (
        ("dashboard-home", "Dashboard Home", "dashboard-overview", "/app/dashboard", 1, DASHBOARD_ACTIONS, ()),
        ("inventory-store-inventory-workspace", "Store Inventory", "inventory-workspace", "/app/items/store-inventory", 1, ALL_ACTIONS, ()),
        ("inventory-production-inventory-workspace", "Production Inventory", "inventory-workspace", "/app/items/production-inventory", 2, ALL_ACTIONS, ()),
        ("blending-stock-workspace", "Blending Stock", "blending-workspace", "/app/blending/stock", 1, ALL_ACTIONS, ()),
        (REQUESTS_SCREEN_CODE, REQUESTS_SCREEN_NAME, REQUESTS_SECTION_CODE, REQUESTS_SCREEN_PATH, 1, ALL_ACTIONS, REQUESTS_SCREEN_ALIASES),
        ("blending-transactions-workspace", "Blending Transactions", "blending-workspace", "/app/blending/transactions", 2, ALL_ACTIONS, ()),
        ("production-ad-weightage-workspace", "AD Weightage", "production-workspace", "/app/production/ad-weightage", 1, ALL_ACTIONS, ()),
        ("production-bl-blending-workspace", "BL Blending", "production-workspace", "/app/production/bl-blending", 2, ALL_ACTIONS, ()),
        ("production-gl-granulation-workspace", "GL Granulation", "production-workspace", "/app/production/gl-granulation", 3, ALL_ACTIONS, ()),
        ("production-pr-production-workspace", "PR Production", "production-workspace", "/app/production/pr-production", 4, ALL_ACTIONS, ()),
        ("store-stock-workspace", "Store Stock", "store-workspace", "/app/store/stock", 1, ALL_ACTIONS, ()),
        ("store-request-workspace", "Request Approval's", "store-workspace", "/app/store/request", 2, ALL_ACTIONS, ()),
        ("store-transactions-workspace", "Store Transactions", "store-workspace", "/app/store/transactions", 3, ALL_ACTIONS, ()),
        ("grn-process-workspace", "GRN Process", "grn-workspace", "/app/grn/process", 1, ALL_ACTIONS, ()),
        ("grn-status-workspace", "GRN Status", "grn-workspace", "/app/grn/status", 2, ALL_ACTIONS, ()),
        ("contacts-workspace", "Contacts", "contacts-workspace", "/app/contacts", 1, ALL_ACTIONS, ()),
        ("regrind-workspace", "Regrind", "regrind-workspace", "/app/regrind", 1, ALL_ACTIONS, ()),
        ("main-screen-master", "Main Screens", "admin-master", "/admin/main-screens", 1, ALL_ACTIONS, ()),
        ("screen-section-master", "Screen Sections", "admin-master", "/admin/screen-sections", 2, ALL_ACTIONS, ()),
        ("user-screen-master", "User Screens", "admin-master", "/admin/user-screens", 3, ALL_ACTIONS, ()),
        ("department-master", "Department", "admin-master", "/wpe-masters/departments", 4, ALL_ACTIONS, ()),
        ("staff-creation-master", "Staff Creation", "admin-master", "/admin/staff-creation", 5, ALL_ACTIONS, ()),
        ("role-master", "Role", "admin-master", "/wpe-masters/roles", 6, ALL_ACTIONS, ()),
        ("user-type-master", "User Type / Role Mapping", "admin-master", "/admin/user-types", 7, ALL_ACTIONS, ()),
        ("user-creation-master", "User Creation", "admin-master", "/admin/user-creation", 8, ALL_ACTIONS, ()),
        ("user-screen-permission-master", "User Type Permissions", "admin-master", "/admin/user-screen-permission", 9, ALL_ACTIONS, ()),
        ("continent-master", "Continent Master", "common-master", "/masters/continents", 1, ALL_ACTIONS, ()),
        ("country-master", "Country Master", "common-master", "/masters/countries", 2, ALL_ACTIONS, ()),
        ("state-master", "State Master", "common-master", "/masters/states", 3, ALL_ACTIONS, ()),
        ("city-master", "City Master", "common-master", "/masters/cities", 4, ALL_ACTIONS, ()),
        ("tax-master", "Tax Master", "common-master", "/masters/taxes", 5, ALL_ACTIONS, ()),
        ("currency-master", "Currency Master", "common-master", "/masters/currencies", 6, ALL_ACTIONS, ()),
        ("customer-master", "Customer Master", "common-master", "/masters/customers", 7, ALL_ACTIONS, ()),
        ("supplier-master", "Supplier Master", "common-master", "/masters/suppliers", 8, ALL_ACTIONS, ()),
        ("company-master", "Company Master", "common-master", "/masters/companies", 9, ALL_ACTIONS, ()),
        ("wpe-product-type-master", "Item Category", "inventory-store-master", "/wpe-masters/product-types", 1, ALL_ACTIONS, ()),
        ("wpe-product-subtype-master", "Item Sub Category", "inventory-store-master", "/wpe-masters/product-subtypes", 2, ALL_ACTIONS, ()),
        ("unit-master", "Unit Master", "inventory-store-master", "/wpe-masters/units", 3, ALL_ACTIONS, ()),
        ("item-creation-master", "Item Variant Master", "inventory-store-master", "/wpe-masters/item-variants", 4, ALL_ACTIONS, ()),
        ("store-master", "Store Master", "inventory-store-master", "/wpe-masters/stores", 5, ALL_ACTIONS, ()),
        ("warehouse-master", "Warehouse Master", "inventory-store-master", "/wpe-masters/warehouses", 6, ALL_ACTIONS, ()),
        ("location-master", "Location Master", "inventory-store-master", "/wpe-masters/locations", 7, ALL_ACTIONS, ()),
        ("production-type-master", "Production Type Master", "inventory-store-master", "/wpe-masters/production-types", 8, ALL_ACTIONS, ()),
        ("sale-type-master", "Sale Type Master", "inventory-store-master", "/wpe-masters/sale-types", 9, ALL_ACTIONS, ()),
        ("purchase-type-master", "Purchase Type Master", "inventory-store-master", "/wpe-masters/purchase-types", 10, ALL_ACTIONS, ()),
        ("profile-creation-master", "Profile Creation Master", "production-master", "/masters/production-masters/profile-creations", 1, ALL_ACTIONS, ()),
        ("profile-size-master", "Profile Size Master", "production-master", "/masters/production-masters/profile-sizes", 2, ALL_ACTIONS, ()),
        ("color-creation-master", "Color Creation Master", "production-master", "/masters/production-masters/color-creations", 3, ALL_ACTIONS, ()),
        ("machine-creation-master", "Machine Creation Master", "production-master", "/masters/production-masters/machine-creations", 4, ALL_ACTIONS, ()),
        ("work-centre-creation-master", "Work Centre Creation Master", "production-master", "/masters/production-masters/work-centre-creations", 5, ALL_ACTIONS, ()),
        ("production-line-master", "Production Line Master", "production-master", "/masters/production-masters/production-lines", 6, ALL_ACTIONS, ()),
        ("bin-creation-master", "Bin Creation Master", "production-master", "/masters/production-masters/bin-creations", 7, ALL_ACTIONS, ()),
        ("bag-creation-master", "Bag Creation Master", "production-master", "/masters/production-masters/bag-creations", 8, ALL_ACTIONS, ()),
        ("packing-type-master", "Packing Type Master", "production-master", "/masters/production-masters/packing-types", 9, ALL_ACTIONS, ()),
        ("packing-material-master", "Packing Material Master", "production-master", "/masters/production-masters/packing-materials", 10, ALL_ACTIONS, ()),
        ("recipe-creation-master", "Recipe Creation Master", "recipe-bom-master", "/masters/recipe-bom-masters/recipe-creations", 1, ALL_ACTIONS, ()),
        ("recipe-item-creation-master", "Recipe Item Creation Master", "recipe-bom-master", "/masters/recipe-bom-masters/recipe-item-creations", 2, ALL_ACTIONS, ()),
        ("bom-creation-master", "BOM Creation Master", "recipe-bom-master", "/masters/recipe-bom-masters/bom-creations", 3, ALL_ACTIONS, ()),
        ("bom-item-creation-master", "BOM Item Creation Master", "recipe-bom-master", "/masters/recipe-bom-masters/bom-item-creations", 4, ALL_ACTIONS, ()),
        ("weighment-scale-master", "Weighment Scale Master", "device-label-master", "/masters/device-label-masters/weighment-scale-creations", 1, ALL_ACTIONS, ()),
        ("printer-master", "Printer Master", "device-label-master", "/masters/device-label-masters/printer-creations", 2, ALL_ACTIONS, ()),
        ("qr-label-template-master", "QR Label Template Master", "device-label-master", "/masters/device-label-masters/qr-label-templates", 3, ALL_ACTIONS, ()),
        ("serial-port-configuration-master", "Serial Port Configuration Master", "device-label-master", "/masters/device-label-masters/serial-port-configurations", 4, ALL_ACTIONS, ()),
    )

    for code, name, section_code, folder_name, order_no, available_actions, aliases in screen_definitions:
        _upsert_screen(
            UserScreen,
            UserTypePermission,
            sections_by_code=sections_by_code,
            code=code,
            name=name,
            section_code=section_code,
            folder_name=folder_name,
            order_no=order_no,
            available_actions=available_actions,
            aliases=aliases,
        )

    requests_section = sections_by_code[REQUESTS_SECTION_CODE]
    inventory_store_section = sections_by_code["inventory-store-master"]

    for obsolete_code, replacement_code in OBSOLETE_SECTION_CODES.items():
        obsolete_section = (
            ScreenSection.objects.filter(code=obsolete_code)
            .exclude(pk=sections_by_code.get(replacement_code).pk if replacement_code else None)
            .first()
        )
        if obsolete_section is None:
            continue

        if replacement_code:
            _merge_section_permissions(
                UserTypePermission,
                source_section_ids=[obsolete_section.id],
                target_section=sections_by_code[replacement_code],
            )
        else:
            UserTypePermission.objects.filter(screen_section_id=obsolete_section.id).delete()

        if not UserScreen.objects.filter(screen_section_id=obsolete_section.id).exists():
            obsolete_section.delete()

    for obsolete_code in OBSOLETE_SCREEN_CODES:
        obsolete_screen = UserScreen.objects.filter(code=obsolete_code).first()
        if obsolete_screen is None:
            continue
        UserTypePermission.objects.filter(user_screen_id=obsolete_screen.id).delete()
        obsolete_screen.delete()

    UserTypePermission.objects.filter(
        screen_section_id=requests_section.id,
        user_screen_id__isnull=True,
        scope_type="screen",
    ).update(user_screen_id=None)

    UserTypePermission.objects.filter(
        screen_section_id=inventory_store_section.id,
        user_screen_id__isnull=True,
        scope_type="screen",
    ).update(user_screen_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0010_rename_item_creation_master_to_item_variant_master"),
    ]

    operations = [
        migrations.RunPython(
            normalize_navigation_permission_screens,
            migrations.RunPython.noop,
        ),
    ]
