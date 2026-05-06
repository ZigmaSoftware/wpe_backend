# Generated manually for GRN item identity support.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Items", "0002_item_stock"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="external_item_id",
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
    ]
