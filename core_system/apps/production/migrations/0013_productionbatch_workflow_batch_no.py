from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0012_alter_productionoutputcapture_quantity_kg_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="productionbatch",
            name="workflow_batch_no",
            field=models.CharField(blank=True, db_index=True, max_length=30, null=True),
        ),
    ]
