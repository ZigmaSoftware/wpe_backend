from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0007_alter_bomvariant_access_password_hash"),
    ]

    operations = [
        migrations.AddField(
            model_name="productionorder",
            name="production_for",
            field=models.CharField(
                blank=True,
                help_text="Production purpose, customer, or internal job reference",
                max_length=255,
                null=True,
            ),
        ),
    ]
