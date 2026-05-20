import django.utils.timezone
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("Purchases_Inwards", "0004_grn_qcr_unique_id_grn_raw_payload"),
    ]

    operations = [
        # Invoice / Order Details
        migrations.AddField(
            model_name="grn",
            name="purchase_bill_no",
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="grn",
            name="purchase_bill_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="grn",
            name="dc_numbers",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="grn",
            name="delivery_days_gap",
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        migrations.AddField(
            model_name="grn",
            name="delivery_note_no",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="grn",
            name="delivery_note_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="grn",
            name="order_rating",
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
        # Warehouse Routing
        migrations.AddField(
            model_name="grn",
            name="grn_warehouse",
            field=models.CharField(blank=True, default="QC Pending Warehouse - CBE", max_length=255),
        ),
        migrations.AddField(
            model_name="grn",
            name="source_warehouse",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="grn",
            name="accepted_warehouse",
            field=models.CharField(blank=True, default="Stores", max_length=255),
        ),
        migrations.AddField(
            model_name="grn",
            name="rejected_warehouse",
            field=models.CharField(blank=True, default="Rejected Warehouse - CBE", max_length=255),
        ),
        # QC Status
        migrations.AddField(
            model_name="grn",
            name="qc_status",
            field=models.CharField(blank=True, default="Pending", max_length=20),
        ),
        # GRN Audit Log model
        migrations.CreateModel(
            name="GRNAuditLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("grn", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_logs", to="Purchases_Inwards.grn")),
                ("stage", models.CharField(max_length=100)),
                ("actor", models.CharField(blank=True, max_length=255, null=True)),
                ("notes", models.TextField(blank=True, null=True)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-timestamp"],
            },
        ),
    ]
