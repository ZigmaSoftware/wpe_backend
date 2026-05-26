from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contacts", "0001_initial"),
    ]

    operations = [
        # Identity
        migrations.AddField(model_name="contact", name="display_name",
            field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(model_name="contact", name="contact_code",
            field=models.CharField(blank=True, default="", max_length=50)),

        # Classification
        migrations.AddField(model_name="contact", name="contact_category",
            field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="contact", name="customer_loyalty",
            field=models.CharField(blank=True, default="", max_length=50,
                choices=[("Platinum", "Platinum"), ("Gold", "Gold"), ("Silver", "Silver"), ("Bronze", "Bronze")])),
        migrations.AddField(model_name="contact", name="division",
            field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="contact", name="zone",
            field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="contact", name="subzone",
            field=models.CharField(blank=True, default="", max_length=100)),

        # Company / Tax
        migrations.AddField(model_name="contact", name="pan",
            field=models.CharField(blank=True, default="", max_length=10)),
        migrations.AddField(model_name="contact", name="accounting_percent",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
        migrations.AddField(model_name="contact", name="tds_category",
            field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="contact", name="tds_percent",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),

        # Sales
        migrations.AddField(model_name="contact", name="sale_person",
            field=models.CharField(blank=True, default="", max_length=255)),

        # Personnel
        migrations.AddField(model_name="contact", name="contact_person",
            field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(model_name="contact", name="designation",
            field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="contact", name="work_phone_2",
            field=models.CharField(blank=True, default="", max_length=20)),
        migrations.AddField(model_name="contact", name="work_phone_3",
            field=models.CharField(blank=True, default="", max_length=20)),
        migrations.AddField(model_name="contact", name="fax",
            field=models.CharField(blank=True, default="", max_length=20)),

        # Billing Address
        migrations.AddField(model_name="contact", name="billing_landmark",
            field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(model_name="contact", name="billing_city",
            field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="contact", name="billing_postal_code",
            field=models.CharField(blank=True, default="", max_length=20)),
        migrations.AddField(model_name="contact", name="billing_country",
            field=models.CharField(blank=True, default="India", max_length=100)),

        # Notes
        migrations.AddField(model_name="contact", name="notes",
            field=models.TextField(blank=True, default="")),
    ]
