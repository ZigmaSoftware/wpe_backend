from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("production", "0010_merge_20260601_1234"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductionOutputCapture",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField()),
                ("scancode_id", models.CharField(db_index=True, max_length=120, unique=True)),
                ("recipe_no", models.CharField(blank=True, max_length=100)),
                ("quantity_kg", models.DecimalField(decimal_places=3, default="0.000", max_digits=14)),
                ("weight_kg", models.DecimalField(decimal_places=3, default="0.000", max_digits=14)),
                ("binlot", models.CharField(blank=True, max_length=100)),
                ("session_key", models.TextField(blank=True)),
                ("captured_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "production_order",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="output_captures", to="production.productionorder"),
                ),
                (
                    "source_batch",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="output_capture", to="production.productionbatch"),
                ),
            ],
            options={
                "ordering": ["-captured_at", "-id"],
                "indexes": [
                    models.Index(fields=["production_order", "captured_at"], name="prod_out_cap_ord_cap_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("production_order", "sequence"), name="prod_out_cap_ord_seq_uq"),
                ],
            },
        ),
    ]
