from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0014_backfill_productionbatch_workflow_batch_no"),
    ]

    operations = [
        migrations.AddField(
            model_name="productionorder",
            name="extra_form_data",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
