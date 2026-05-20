import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0001_initial"),
        ("Items", "0003_item_external_item_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductionMachine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("machine_code", models.CharField(max_length=30, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("machine_type", models.CharField(choices=[("HIGH_SPEED_MIX", "High Speed Mix"), ("GRANULATOR", "Granulator")], max_length=30)),
                ("applicable_stages", models.CharField(default="AD,BL", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("location", models.CharField(blank=True, max_length=100)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["machine_code"]},
        ),
        migrations.CreateModel(
            name="BOMVariant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("variant_code", models.CharField(max_length=30, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("revision", models.CharField(default="v1", max_length=10)),
                ("is_active", models.BooleanField(default=True)),
                ("access_password_hash", models.CharField(max_length=64)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("product_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bom_variants", to="Items.item")),
            ],
            options={"ordering": ["variant_code"]},
        ),
        migrations.CreateModel(
            name="BOMVariantComponent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target_weight_grams", models.DecimalField(decimal_places=3, max_digits=10)),
                ("min_weight_grams", models.DecimalField(decimal_places=3, max_digits=10)),
                ("max_weight_grams", models.DecimalField(decimal_places=3, max_digits=10)),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("is_regrind", models.BooleanField(default=False)),
                ("unit", models.CharField(default="g", max_length=20)),
                ("bom_variant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="components", to="production.bomvariant")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="Items.item")),
            ],
            options={"ordering": ["sequence"], "unique_together": {("bom_variant", "item")}},
        ),
        migrations.CreateModel(
            name="ProductionBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("batch_no", models.CharField(blank=True, max_length=30, unique=True)),
                ("stage", models.CharField(choices=[("AD", "Raw Materials (AD)"), ("BL", "Blending (BL)"), ("GL", "Granulation (GL)")], max_length=10)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("IN_PROGRESS", "In Progress"), ("COMPLETED", "Completed"), ("FAILED", "Failed")], default="PENDING", max_length=20)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("bom_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="production.bomvariant")),
                ("machine", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="production.productionmachine")),
                ("operator", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("production_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="batches", to="production.productionorder")),
            ],
            options={"ordering": ["stage", "-created_at"]},
        ),
        migrations.CreateModel(
            name="BatchWeightEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target_weight_grams", models.DecimalField(decimal_places=3, max_digits=10)),
                ("entered_weight_grams", models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True)),
                ("is_valid", models.BooleanField(blank=True, null=True)),
                ("validation_notes", models.TextField(blank=True)),
                ("source", models.CharField(default="MANUAL", max_length=20)),
                ("entered_at", models.DateTimeField(auto_now_add=True)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="weight_entries", to="production.productionbatch")),
                ("bom_component", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="production.bomvariantcomponent")),
                ("entered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="Items.item")),
            ],
            options={"unique_together": {("batch", "bom_component")}},
        ),
        migrations.CreateModel(
            name="RegrindMaterialEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stage", models.CharField(choices=[("AD", "Raw Materials (AD)"), ("BL", "Blending (BL)"), ("GL", "Granulation (GL)")], max_length=10)),
                ("quantity_grams", models.DecimalField(decimal_places=3, max_digits=10)),
                ("source_lot_no", models.CharField(blank=True, max_length=50)),
                ("is_valid", models.BooleanField(default=True)),
                ("validation_notes", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("added_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="regrind_entries", to="production.productionbatch")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="Items.item")),
                ("production_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="regrind_entries", to="production.productionorder")),
            ],
            options={"ordering": ["-added_at"]},
        ),
    ]
