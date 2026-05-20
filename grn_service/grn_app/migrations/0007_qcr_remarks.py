from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Purchases_Inwards", "0006_alter_grnauditlog_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="qcr",
            name="remarks",
            field=models.TextField(blank=True, null=True),
        ),
    ]
