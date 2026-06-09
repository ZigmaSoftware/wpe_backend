from django.db import migrations


def rename_item_creation_master(apps, schema_editor):
    UserScreen = apps.get_model("admin_master", "UserScreen")
    UserScreen.objects.filter(code="item-creation-master").update(
        screen_name="Item Variant Master",
        folder_name="/wpe-masters/item-variants",
    )


def revert_item_variant_master(apps, schema_editor):
    UserScreen = apps.get_model("admin_master", "UserScreen")
    UserScreen.objects.filter(code="item-creation-master").update(
        screen_name="Item Creation Master",
        folder_name="/wpe-masters/item-creations",
    )


class Migration(migrations.Migration):

    dependencies = [
        ('admin_master', '0009_rename_store_request_workspace_label'),
    ]

    operations = [
        migrations.RunPython(rename_item_creation_master, revert_item_variant_master),
    ]
