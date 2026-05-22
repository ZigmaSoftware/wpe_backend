from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("Items", "0003_item_external_item_id"),
        ("production", "0003_alter_bomvariantcomponent_unique_together_and_more"),
        ("wpe_masters", "0006_seed_product_types"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductionOrderMaterialPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("source_type", models.CharField(choices=[("ITEM", "Item"), ("PRODUCT_SUBTYPE", "Product Subtype")], default="ITEM", max_length=20)),
                ("is_bom_derived", models.BooleanField(default=False)),
                ("is_manual", models.BooleanField(default=False)),
                ("item_code", models.CharField(blank=True, max_length=100)),
                ("item_name", models.CharField(max_length=255)),
                ("unit", models.CharField(default="g", max_length=20)),
                ("per_unit_quantity", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("bom_quantity", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("required_quantity", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("received_quantity", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("remaining_quantity", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("request_quantity", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("rate", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("bom_component", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="production.bomvariantcomponent")),
                ("bom_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="production.bomvariant")),
                ("item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="Items.item")),
                ("product_subtype", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="production_material_plans", to="wpe_masters.producttypesubtype")),
                ("production_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="material_plans", to="production.productionorder")),
            ],
            options={
                "ordering": ["sequence", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="productionordermaterialplan",
            index=models.Index(fields=["production_order", "sequence"], name="prod_material_order_seq_idx"),
        ),
        migrations.AddIndex(
            model_name="productionordermaterialplan",
            index=models.Index(fields=["bom_variant"], name="prod_material_bom_idx"),
        ),
    ]
