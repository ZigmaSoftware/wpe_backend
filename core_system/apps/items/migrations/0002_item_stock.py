# Generated manually for item code generation and stock movement support.

from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Items", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="product_type",
            field=models.CharField(blank=True, default="General Item", max_length=100),
        ),
        migrations.AddField(
            model_name="item",
            name="opening_stock",
            field=models.DecimalField(decimal_places=3, default=Decimal("0.000"), max_digits=14),
        ),
        migrations.AddField(
            model_name="item",
            name="current_stock",
            field=models.DecimalField(decimal_places=3, default=Decimal("0.000"), max_digits=14),
        ),
        migrations.AlterField(
            model_name="item",
            name="item_code",
            field=models.CharField(blank=True, editable=False, max_length=100, unique=True),
        ),
        migrations.AddIndex(
            model_name="item",
            index=models.Index(
                fields=["category", "group", "sub_group", "unit"],
                name="items_identity_lookup_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="item",
            index=models.Index(fields=["product_type", "item_code"], name="items_type_code_idx"),
        ),
        migrations.CreateModel(
            name="ItemStockTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(default=django.utils.timezone.localdate)),
                ("ref_id", models.CharField(blank=True, max_length=100, null=True)),
                ("trans_type", models.CharField(max_length=150)),
                ("sale_type", models.CharField(blank=True, max_length=100, null=True)),
                ("doc_id", models.CharField(blank=True, max_length=100, null=True)),
                ("contact", models.CharField(blank=True, max_length=255, null=True)),
                ("warehouse", models.CharField(blank=True, max_length=150, null=True)),
                ("bin", models.CharField(blank=True, max_length=100, null=True)),
                ("inwards", models.DecimalField(decimal_places=3, default=Decimal("0.000"), max_digits=14)),
                ("outwards", models.DecimalField(decimal_places=3, default=Decimal("0.000"), max_digits=14)),
                ("balance", models.DecimalField(decimal_places=3, default=Decimal("0.000"), max_digits=14)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_transactions",
                        to="Items.item",
                    ),
                ),
            ],
            options={
                "ordering": ["date", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="itemstocktransaction",
            index=models.Index(fields=["item", "date"], name="items_tx_item_date_idx"),
        ),
        migrations.AddIndex(
            model_name="itemstocktransaction",
            index=models.Index(fields=["ref_id"], name="items_tx_ref_idx"),
        ),
        migrations.AddIndex(
            model_name="itemstocktransaction",
            index=models.Index(fields=["trans_type"], name="items_tx_type_idx"),
        ),
        migrations.AddIndex(
            model_name="itemstocktransaction",
            index=models.Index(fields=["warehouse", "bin"], name="items_tx_wh_bin_idx"),
        ),
    ]
