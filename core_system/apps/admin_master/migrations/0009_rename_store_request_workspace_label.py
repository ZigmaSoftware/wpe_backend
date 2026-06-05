from django.db import migrations


def rename_store_request_workspace_label(apps, schema_editor):
    UserScreen = apps.get_model("admin_master", "UserScreen")
    UserScreen.objects.filter(code="store-request-workspace").update(
        screen_name="Request Approval's"
    )


def reverse_store_request_workspace_label(apps, schema_editor):
    UserScreen = apps.get_model("admin_master", "UserScreen")
    UserScreen.objects.filter(code="store-request-workspace").update(
        screen_name="Store Request"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0008_seed_navigation_permission_screens"),
    ]

    operations = [
        migrations.RunPython(
            rename_store_request_workspace_label,
            reverse_store_request_workspace_label,
        ),
    ]
