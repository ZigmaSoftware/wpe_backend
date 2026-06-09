from django.db import migrations


ALL_ACTIONS = ["add", "update", "list", "delete", "view", "print"]


def add_designation_admin_screen(apps, schema_editor):
    MainScreen = apps.get_model("admin_master", "MainScreen")
    ScreenSection = apps.get_model("admin_master", "ScreenSection")
    UserScreen = apps.get_model("admin_master", "UserScreen")

    masters_main, _ = MainScreen.objects.get_or_create(
        code="masters",
        defaults={"name": "Masters", "order_no": 3, "status": True},
    )
    if masters_main.name != "Masters" or masters_main.order_no != 3 or not masters_main.status:
        masters_main.name = "Masters"
        masters_main.order_no = 3
        masters_main.status = True
        masters_main.save(update_fields=["name", "order_no", "status"])

    admin_section, _ = ScreenSection.objects.get_or_create(
        code="admin-master",
        defaults={
            "name": "Admin Masters",
            "main_screen": masters_main,
            "order_no": 1,
            "is_active": True,
        },
    )
    section_updates = []
    if admin_section.name != "Admin Masters":
        admin_section.name = "Admin Masters"
        section_updates.append("name")
    if admin_section.main_screen_id != masters_main.id:
        admin_section.main_screen = masters_main
        section_updates.append("main_screen")
    if admin_section.order_no != 1:
        admin_section.order_no = 1
        section_updates.append("order_no")
    if not admin_section.is_active:
        admin_section.is_active = True
        section_updates.append("is_active")
    if section_updates:
        admin_section.save(update_fields=section_updates)

    screen_definitions = (
        ("main-screen-master", "Main Screens", "/admin/main-screens", 1),
        ("screen-section-master", "Screen Sections", "/admin/screen-sections", 2),
        ("user-screen-master", "User Screens", "/admin/user-screens", 3),
        ("department-master", "Department", "/wpe-masters/departments", 4),
        ("designation-master", "Desigination", "/wpe-masters/designations", 5),
        ("staff-creation-master", "Staff Creation", "/admin/staff-creation", 6),
        ("role-master", "Role", "/wpe-masters/roles", 7),
        ("user-type-master", "User Type / Role Mapping", "/admin/user-types", 8),
        ("user-creation-master", "User Creation", "/admin/user-creation", 9),
        ("user-screen-permission-master", "User Type Permissions", "/admin/user-screen-permission", 10),
    )

    for code, screen_name, folder_name, order_no in screen_definitions:
        screen, created = UserScreen.objects.get_or_create(
            code=code,
            defaults={
                "main_screen": masters_main,
                "screen_section": admin_section,
                "screen_name": screen_name,
                "folder_name": folder_name,
                "order_no": order_no,
                "is_active": True,
                "available_actions": ALL_ACTIONS,
            },
        )
        if created:
            continue

        updates = []
        if screen.main_screen_id != masters_main.id:
            screen.main_screen = masters_main
            updates.append("main_screen")
        if screen.screen_section_id != admin_section.id:
            screen.screen_section = admin_section
            updates.append("screen_section")
        if screen.screen_name != screen_name:
            screen.screen_name = screen_name
            updates.append("screen_name")
        if screen.folder_name != folder_name:
            screen.folder_name = folder_name
            updates.append("folder_name")
        if screen.order_no != order_no:
            screen.order_no = order_no
            updates.append("order_no")
        if not screen.is_active:
            screen.is_active = True
            updates.append("is_active")
        if list(screen.available_actions or []) != ALL_ACTIONS:
            screen.available_actions = ALL_ACTIONS
            updates.append("available_actions")
        if updates:
            screen.save(update_fields=updates)


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0011_move_blending_store_request_to_requests_workspace"),
    ]

    operations = [
        migrations.RunPython(add_designation_admin_screen, migrations.RunPython.noop),
    ]
