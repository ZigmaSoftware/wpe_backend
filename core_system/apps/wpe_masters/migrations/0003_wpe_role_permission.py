import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0001_initial"),
        ("wpe_masters", "0002_seed_masters"),
    ]

    operations = [
        migrations.CreateModel(
            name="WPERolePermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("view_all", models.BooleanField(default=False)),
                ("view_self", models.BooleanField(default=False)),
                ("can_add", models.BooleanField(default=False)),
                ("can_edit", models.BooleanField(default=False)),
                ("can_duplicate", models.BooleanField(default=False)),
                ("can_delete", models.BooleanField(default=False)),
                ("generate_invoice_access", models.BooleanField(default=False)),
                ("invoice_access", models.BooleanField(default=False)),
                ("access", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("main_screen", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_permissions", to="admin_master.mainscreen")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="screen_permissions", to="wpe_masters.rolemaster")),
            ],
            options={
                "verbose_name": "WPE Role Permission",
                "verbose_name_plural": "WPE Role Permissions",
                "db_table": "wpe_role_permission",
                "ordering": ["main_screen__order_no", "role__name"],
            },
        ),
        migrations.AddConstraint(
            model_name="wperolepermission",
            constraint=models.UniqueConstraint(fields=("role", "main_screen"), name="unique_role_main_screen"),
        ),
    ]
