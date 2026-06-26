from django.db import migrations


ALL_ACTIONS = ["add", "update", "list", "delete", "view", "print"]
HEAD_APPROVAL_ACTIONS = ["list", "view", "update"]


def _merge_action_permissions(current, incoming):
    current_map = current or {}
    incoming_map = incoming or {}
    keys = ("all", "add", "update", "list", "delete", "view", "print")
    return {key: bool(current_map.get(key) or incoming_map.get(key)) for key in keys}


def _find_section(ScreenSection, *, main_screen_id, candidates):
    for code in candidates:
        if not code:
            continue
        section = ScreenSection.objects.filter(main_screen_id=main_screen_id, code=code).first()
        if section:
            return section
    for name in candidates:
        if not name:
            continue
        section = ScreenSection.objects.filter(main_screen_id=main_screen_id, name=name).first()
        if section:
            return section
    return None


def _ensure_section(ScreenSection, *, main_screen, code, name, order_no, aliases=()):
    section = _find_section(
        ScreenSection,
        main_screen_id=main_screen.id,
        candidates=(code, *aliases, name),
    )

    if section is None:
        return ScreenSection.objects.create(
            main_screen=main_screen,
            code=code,
            name=name,
            order_no=order_no,
            is_active=True,
        )

    updates = []
    if not section.code:
        section.code = code
        updates.append("code")
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


def _ensure_screen(
    UserScreen,
    UserTypePermission,
    *,
    code,
    screen_name,
    section,
    route_path,
    order_no,
    available_actions,
):
    screen = UserScreen.objects.filter(code=code).first()
    if screen is None:
        screen = UserScreen.objects.create(
            main_screen=section.main_screen,
            screen_section=section,
            screen_name=screen_name,
            code=code,
            folder_name=route_path,
            order_no=order_no,
            is_active=True,
            available_actions=available_actions,
        )
    else:
        updates = []
        if screen.main_screen_id != section.main_screen_id:
            screen.main_screen = section.main_screen
            updates.append("main_screen")
        if screen.screen_section_id != section.id:
            screen.screen_section = section
            updates.append("screen_section")
        if screen.screen_name != screen_name:
            screen.screen_name = screen_name
            updates.append("screen_name")
        if screen.folder_name != route_path:
            screen.folder_name = route_path
            updates.append("folder_name")
        if screen.order_no != order_no:
            screen.order_no = order_no
            updates.append("order_no")
        if not screen.is_active:
            screen.is_active = True
            updates.append("is_active")
        if list(screen.available_actions or []) != list(available_actions):
            screen.available_actions = list(available_actions)
            updates.append("available_actions")
        if updates:
            screen.save(update_fields=updates)

    UserTypePermission.objects.filter(user_screen_id=screen.id).update(
        main_screen_id=screen.main_screen_id,
        screen_section_id=screen.screen_section_id,
    )
    return screen


def _sync_warehouse_permissions(UserTypePermission, UserScreen, warehouse_screen):
    source_rows = (
        UserTypePermission.objects.filter(
            scope_type="screen",
            user_screen_id__in=list(
                UserScreen.objects.filter(
                    code__in=(
                        "inventory-store-inventory-workspace",
                        "inventory-production-inventory-workspace",
                    )
                ).values_list("id", flat=True)
            ),
        )
        .order_by("user_type_id", "id")
    )

    permission_by_user_type = {}
    for row in source_rows:
        cached = permission_by_user_type.get(row.user_type_id)
        if cached is None:
            permission_by_user_type[row.user_type_id] = {
                "status": bool(row.status),
                "action_permissions": dict(row.action_permissions or {}),
            }
            continue

        cached["status"] = bool(cached["status"] or row.status)
        cached["action_permissions"] = _merge_action_permissions(
            cached["action_permissions"],
            row.action_permissions,
        )

    for user_type_id, payload in permission_by_user_type.items():
        permission_key = f"{user_type_id}:screen:{warehouse_screen.id}"
        UserTypePermission.objects.update_or_create(
            permission_key=permission_key,
            defaults={
                "user_type_id": user_type_id,
                "main_screen_id": warehouse_screen.main_screen_id,
                "screen_section_id": warehouse_screen.screen_section_id,
                "user_screen_id": warehouse_screen.id,
                "scope_type": "screen",
                "action_permissions": payload["action_permissions"],
                "status": payload["status"],
            },
        )


def sync_current_workspace_rbac(apps, schema_editor):
    MainScreen = apps.get_model("admin_master", "MainScreen")
    ScreenSection = apps.get_model("admin_master", "ScreenSection")
    UserScreen = apps.get_model("admin_master", "UserScreen")
    UserTypePermission = apps.get_model("admin_master", "UserTypePermission")

    workspace_main = MainScreen.objects.filter(code="workspace").first()
    if workspace_main is None:
        workspace_main = MainScreen.objects.create(
            code="workspace",
            name="WPE Workspace",
            order_no=2,
            status=True,
        )

    inventory_section = _ensure_section(
        ScreenSection,
        main_screen=workspace_main,
        code="inventory-workspace",
        name="Inventory Workspace",
        order_no=1,
    )
    requests_section = _ensure_section(
        ScreenSection,
        main_screen=workspace_main,
        code="requests-workspace",
        name="Requests",
        order_no=8,
        aliases=("requests",),
    )

    warehouse_screen = _ensure_screen(
        UserScreen,
        UserTypePermission,
        code="inventory-warehouse-inventory-workspace",
        screen_name="Warehouse Inventory",
        section=inventory_section,
        route_path="/app/items/warehouse-inventory",
        order_no=3,
        available_actions=ALL_ACTIONS,
    )

    _ensure_screen(
        UserScreen,
        UserTypePermission,
        code="blending-head-approval-workspace",
        screen_name="Head Approval's",
        section=requests_section,
        route_path="/app/requests/head-approval",
        order_no=2,
        available_actions=HEAD_APPROVAL_ACTIONS,
    )

    _sync_warehouse_permissions(UserTypePermission, UserScreen, warehouse_screen)


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0020_seed_role_table_columns"),
    ]

    operations = [
        migrations.RunPython(sync_current_workspace_rbac, migrations.RunPython.noop),
    ]
