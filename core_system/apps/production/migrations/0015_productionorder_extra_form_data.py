from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0013_add_extra_form_data_to_production_order"),
        ("production", "0014_backfill_productionbatch_workflow_batch_no"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productionorder",
            name="extra_form_data",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Stores additional form fields (stage, resources, plan rows, finished goods, etc.)",
                null=True,
            ),
        ),
    ]
