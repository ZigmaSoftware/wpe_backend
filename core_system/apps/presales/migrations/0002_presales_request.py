import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Presales", "0001_initial"),
        ("Items", "0003_item_external_item_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PresalesRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_no", models.CharField(blank=True, max_length=20, unique=True)),
                ("request_date", models.DateField()),
                ("category", models.CharField(choices=[("STORE", "Store"), ("PURCHASE", "Purchase")], max_length=20)),
                ("request_person", models.CharField(max_length=255)),
                ("department", models.CharField(max_length=100)),
                ("required_reason", models.TextField()),
                ("customer_type", models.CharField(default="ADDITIVE_MO", max_length=50)),
                ("customer_name", models.CharField(blank=True, max_length=255)),
                ("remarks", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("SUBMITTED", "Submitted for Approval"), ("APPROVED", "Approved"), ("REJECTED", "Rejected"), ("SENT_TO_PRODUCTION", "Sent to Production")], default="DRAFT", max_length=30)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("approval_remarks", models.TextField(blank=True)),
                ("sent_to_prod_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_presales_requests", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_presales_requests", to=settings.AUTH_USER_MODEL)),
                ("sent_to_prod_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sent_presales_requests", to=settings.AUTH_USER_MODEL)),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_presales_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PresalesRequestItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=14)),
                ("unit", models.CharField(blank=True, max_length=20)),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="Items.item")),
                ("presales_request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="Presales.presalesrequest")),
            ],
        ),
        migrations.CreateModel(
            name="PresalesAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=50)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("performed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("presales_request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_logs", to="Presales.presalesrequest")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
