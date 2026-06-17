from django.db import migrations

ROLE_SCREEN_CODE = "role-master"

ROLE_TABLE_COLUMNS = [
    {"key": "code", "title": "Role Code", "field": "code"},
    {"key": "name", "title": "Role Name", "field": "name"},
    {"key": "designation_name", "title": "Designation", "field": "designation_name"},
    {"key": "is_active", "title": "Status", "field": "is_active"},
]


def seed_role_table_columns(apps, schema_editor):
    UserScreen = apps.get_model("admin_master", "UserScreen")
    UserScreen.objects.filter(code=ROLE_SCREEN_CODE).update(table_columns=ROLE_TABLE_COLUMNS)


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0019_userscreen_table_columns"),
    ]

    operations = [
        migrations.RunPython(seed_role_table_columns, migrations.RunPython.noop),
    ]
