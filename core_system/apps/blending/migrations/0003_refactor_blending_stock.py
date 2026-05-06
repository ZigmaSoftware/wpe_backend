from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def backfill_blending_stock(apps, schema_editor):
    DepartmentStock = apps.get_model("blending", "DepartmentStock")
    BlendingStock = apps.get_model("blending", "BlendingStock")

    blending_rows = []
    for legacy_stock in DepartmentStock.objects.filter(department="BLENDING").only("item_id", "quantity"):
        blending_rows.append(
            BlendingStock(
                item_id=legacy_stock.item_id,
                quantity=legacy_stock.quantity,
            )
        )

    BlendingStock.objects.bulk_create(blending_rows, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("Items", "0002_item_stock"),
        ("blending", "0002_backfill_store_stock"),
        ("store", "0002_backfill_store_stock"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlendingStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=3,
                        default=Decimal("0.000"),
                        max_digits=14,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.000"))],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "item",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="blending_stock",
                        to="Items.item",
                    ),
                ),
            ],
            options={
                "ordering": ["item_id"],
            },
        ),
        migrations.RunPython(backfill_blending_stock, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="DepartmentStock"),
                migrations.DeleteModel(name="StockTransfer"),
            ],
            database_operations=[],
        ),
    ]

