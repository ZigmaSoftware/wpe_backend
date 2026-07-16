from django.db import migrations


def add_tare_master_screen(apps, schema_editor):
    ScreenSection = apps.get_model("admin_master", "ScreenSection")
    UserScreen = apps.get_model("admin_master", "UserScreen")

    production_master_section = ScreenSection.objects.filter(code="production-master").first()
    if not production_master_section:
        return

    UserScreen.objects.get_or_create(
        code="tare-master",
        defaults={
            "main_screen": production_master_section.main_screen,
            "screen_section": production_master_section,
            "screen_name": "Tare Master",
            "folder_name": "/masters/production-masters/tare-masters",
            "order_no": 11,
            "is_active": True,
            "available_actions": ["add", "update", "list", "delete", "view", "print"],
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0021_sync_current_workspace_rbac"),
    ]

    operations = [
        migrations.RunPython(add_tare_master_screen, migrations.RunPython.noop),
    ]
