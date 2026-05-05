# Generated manually for department-based stock support.

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("Items", "0002_item_stock"),
    ]

    operations = [
        migrations.CreateModel(
            name="DepartmentStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "department",
                    models.CharField(
                        choices=[("STORE", "Store"), ("BLENDING", "Blending")],
                        default="STORE",
                        max_length=20,
                    ),
                ),
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
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="department_stocks",
                        to="Items.item",
                    ),
                ),
            ],
            options={
                "ordering": ["item_id", "department"],
                "unique_together": {("item", "department")},
            },
        ),
        migrations.CreateModel(
            name="StockTransfer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "from_department",
                    models.CharField(choices=[("STORE", "Store"), ("BLENDING", "Blending")], max_length=20),
                ),
                (
                    "to_department",
                    models.CharField(choices=[("STORE", "Store"), ("BLENDING", "Blending")], max_length=20),
                ),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=3,
                        max_digits=14,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.001"))],
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("PENDING", "Pending"), ("COMPLETED", "Completed"), ("REJECTED", "Rejected")],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_transfers",
                        to="Items.item",
                    ),
                ),
            ],
            options={
                "ordering": ["-requested_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="departmentstock",
            index=models.Index(fields=["department", "item"], name="blend_dept_item_idx"),
        ),
        migrations.AddIndex(
            model_name="stocktransfer",
            index=models.Index(fields=["item", "status"], name="blend_transfer_item_status_idx"),
        ),
        migrations.AddIndex(
            model_name="stocktransfer",
            index=models.Index(fields=["requested_at"], name="blend_transfer_requested_idx"),
        ),
    ]
