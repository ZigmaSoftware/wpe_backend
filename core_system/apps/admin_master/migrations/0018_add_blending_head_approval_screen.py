from django.db import migrations


def add_blending_head_approval_screen(apps, schema_editor):
    ScreenSection = apps.get_model("admin_master", "ScreenSection")
    UserScreen = apps.get_model("admin_master", "UserScreen")
    UserType = apps.get_model("admin_master", "UserType")
    UserTypePermission = apps.get_model("admin_master", "UserTypePermission")

    blending_section = ScreenSection.objects.filter(code="blending-workspace").first()
    if not blending_section:
        return

    screen, _ = UserScreen.objects.update_or_create(
        code="blending-head-approval-workspace",
        defaults={
            "main_screen": blending_section.main_screen,
            "screen_section": blending_section,
            "screen_name": "Blending Head Approval",
            "folder_name": "/app/blending/head-approval",
            "order_no": 3,
            "is_active": True,
            "available_actions": ["list", "view", "update"],
        },
    )

    user_type = UserType.objects.filter(code="BLENDING_HEAD").first()
    if not user_type:
        return

    UserTypePermission.objects.update_or_create(
        permission_key=f"{user_type.id}:screen:{screen.id}",
        defaults={
            "user_type": user_type,
            "main_screen": screen.main_screen,
            "screen_section": screen.screen_section,
            "user_screen": screen,
            "scope_type": "screen",
            "action_permissions": {
                "all": False,
                "add": False,
                "update": True,
                "list": True,
                "delete": False,
                "view": True,
                "print": False,
            },
            "status": True,
        },
    )

    UserTypePermission.objects.filter(
        user_type=user_type,
        user_screen__code="requests-store-request-workspace",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0017_grant_blending_head_requests_permission"),
    ]

    operations = [
        migrations.RunPython(add_blending_head_approval_screen, migrations.RunPython.noop),
    ]
