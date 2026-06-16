from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0018_bin_current_status_default_free"),
    ]

    operations = [
        migrations.AddField(
            model_name="productionbatch",
            name="parent_batch",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="child_batches",
                to="production.productionbatch",
            ),
        ),
    ]
