from django.db import migrations, models
import apps.admin_master.models


class Migration(migrations.Migration):

    dependencies = [
        ("admin_master", "0018_add_blending_head_approval_screen"),
    ]

    operations = [
        migrations.AddField(
            model_name="userscreen",
            name="table_columns",
            field=models.JSONField(blank=True, default=apps.admin_master.models.default_table_columns),
        ),
    ]
