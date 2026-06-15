from __future__ import annotations

from django.db import migrations


def remove_staff_submodule_data(apps, schema_editor):
    ScreenSection = apps.get_model("admin_master", "ScreenSection")
    UserScreen = apps.get_model("admin_master", "UserScreen")
    UserTypePermission = apps.get_model("admin_master", "UserTypePermission")

    UserTypePermission.objects.filter(user_screen__code="staff-master").delete()
    UserScreen.objects.filter(code="staff-master").delete()

    hr_section = (
        ScreenSection.objects.filter(code="hr-master").first()
        or ScreenSection.objects.filter(name="HR Master").first()
    )
    if hr_section and not UserScreen.objects.filter(screen_section_id=hr_section.id).exists():
        UserTypePermission.objects.filter(screen_section_id=hr_section.id).delete()
        hr_section.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0002_alter_mainscreen_options_alter_role_options_and_more"),
    ]

    operations = [
        migrations.RunPython(remove_staff_submodule_data, migrations.RunPython.noop),
    ]
