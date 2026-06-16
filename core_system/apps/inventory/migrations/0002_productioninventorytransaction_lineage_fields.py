from django.db import migrations, models
import django.db.models.deletion


def populate_movement_keys(apps, schema_editor):
    ProductionInventoryTransaction = apps.get_model("inventory", "ProductionInventoryTransaction")
    for row in ProductionInventoryTransaction.objects.all().only("id"):
        ProductionInventoryTransaction.objects.filter(pk=row.pk).update(movement_key=f"legacy-{row.pk}")


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0019_productionbatch_parent_batch"),
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="productioninventorytransaction",
            name="movement_key",
            field=models.CharField(blank=True, db_index=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name="productioninventorytransaction",
            name="output_capture",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="inventory_transactions",
                to="production.productionoutputcapture",
            ),
        ),
        migrations.AddField(
            model_name="productioninventorytransaction",
            name="production_id",
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name="productioninventorytransaction",
            name="production_order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="inventory_transactions",
                to="production.productionorder",
            ),
        ),
        migrations.AddField(
            model_name="productioninventorytransaction",
            name="production_type",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="productioninventorytransaction",
            name="source_batch",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="inventory_transactions",
                to="production.productionbatch",
            ),
        ),
        migrations.RunPython(populate_movement_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="productioninventorytransaction",
            name="movement_key",
            field=models.CharField(db_index=True, max_length=150, unique=True),
        ),
    ]
