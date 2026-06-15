from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("admin_master", "0010_rename_item_creation_master_to_item_variant_master"),
    ]

    operations = [
        migrations.AddField(
            model_name="usercreation",
            name="password",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
    ]
