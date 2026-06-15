from __future__ import annotations

from django.db import migrations


def rename_screen(
    apps,
    *,
    old_code: str,
    new_code: str,
    old_name: str,
    new_name: str,
):
    UserScreen = apps.get_model("admin_master", "UserScreen")
    UserTypePermission = apps.get_model("admin_master", "UserTypePermission")

    old_screen = UserScreen.objects.filter(code=old_code).first() or UserScreen.objects.filter(screen_name=old_name).first()
    new_screen = UserScreen.objects.filter(code=new_code).first()

    target_screen = new_screen or old_screen

    if old_screen and new_screen and old_screen.pk != new_screen.pk:
        screen_permissions = UserTypePermission.objects.filter(user_screen_id=old_screen.pk)
        for permission in screen_permissions:
            permission.user_screen = new_screen
            permission.main_screen = new_screen.main_screen
            permission.screen_section = new_screen.screen_section
            if permission.scope_type == "screen":
                permission.permission_key = f"{permission.user_type_id}:screen:{new_screen.id}"
            permission.save(
                update_fields=["user_screen", "main_screen", "screen_section", "permission_key"],
            )
        old_screen.delete()
        target_screen = new_screen

    if target_screen:
        update_fields: list[str] = []
        if target_screen.code != new_code:
            target_screen.code = new_code
            update_fields.append("code")
        if target_screen.screen_name != new_name:
            target_screen.screen_name = new_name
            update_fields.append("screen_name")
        if getattr(target_screen, "folder_name", None) != new_code:
            target_screen.folder_name = new_code
            update_fields.append("folder_name")
        if update_fields:
            target_screen.save(update_fields=update_fields)


def rename_user_admin_screens(apps, schema_editor):
    rename_screen(
        apps,
        old_code="user-account-master",
        new_code="user-creation-master",
        old_name="User Account Master",
        new_name="User Creation Master",
    )
    rename_screen(
        apps,
        old_code="user-permission-master",
        new_code="user-screen-permission-master",
        old_name="User Permission Master",
        new_name="User Screen Permission Master",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0003_remove_staff_submodule"),
    ]

    operations = [
        migrations.RunPython(rename_user_admin_screens, migrations.RunPython.noop),
    ]
