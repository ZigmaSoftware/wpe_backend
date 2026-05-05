# Generated manually to activate the existing Items schema.

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Item",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(max_length=150)),
                ("group", models.CharField(max_length=150)),
                ("sub_group", models.CharField(max_length=150)),
                ("item_name", models.CharField(max_length=255)),
                ("item_code", models.CharField(max_length=100, unique=True)),
                ("hsn_code", models.CharField(blank=True, max_length=50, null=True)),
                ("unit", models.CharField(max_length=50)),
                ("product_details", models.TextField(blank=True, null=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("min_max_status", models.BooleanField(default=False)),
                ("status", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
