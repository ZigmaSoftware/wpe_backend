from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0002_backfill_store_stock"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockrequest",
            name="department",
            field=models.CharField(default="BLENDING", max_length=100),
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="request_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="request_type",
            field=models.CharField(
                choices=[("GENERAL", "General"), ("ADDITIVE", "Additive")],
                default="GENERAL",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="requested_for_name",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
