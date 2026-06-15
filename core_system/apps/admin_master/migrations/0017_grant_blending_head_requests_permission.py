from django.db import migrations


def grant_blending_head_requests_permission(apps, schema_editor):
    UserScreen = apps.get_model("admin_master", "UserScreen")
    UserType = apps.get_model("admin_master", "UserType")
    UserTypePermission = apps.get_model("admin_master", "UserTypePermission")

    user_type = UserType.objects.filter(code="BLENDING_HEAD").first()
    requests_screen = UserScreen.objects.filter(code="requests-store-request-workspace").first()
    if not user_type or not requests_screen:
        return

    UserTypePermission.objects.update_or_create(
        permission_key=f"{user_type.id}:screen:{requests_screen.id}",
        defaults={
            "user_type": user_type,
            "main_screen": requests_screen.main_screen,
            "screen_section": requests_screen.screen_section,
            "user_screen": requests_screen,
            "scope_type": "screen",
            "action_permissions": {
                "all": False,
                "add": False,
                "update": False,
                "list": True,
                "delete": False,
                "view": True,
                "print": False,
            },
            "status": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0016_seed_blending_head_approval_master_data"),
    ]

    operations = [
        migrations.RunPython(grant_blending_head_requests_permission, migrations.RunPython.noop),
    ]
