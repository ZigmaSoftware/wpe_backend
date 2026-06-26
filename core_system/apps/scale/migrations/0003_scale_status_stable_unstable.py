from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scale", "0002_device_workstation_identity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scalebridgereading",
            name="status",
            field=models.CharField(
                choices=[
                    ("connected", "Connected"),
                    ("stable", "Stable"),
                    ("unstable", "Unstable"),
                    ("disconnected", "Disconnected"),
                    ("error", "Error"),
                    ("no_serial_port", "No Serial Port"),
                    ("invalid_reading", "Invalid Reading"),
                    ("bridge_not_reporting", "Bridge Not Reporting"),
                ],
                default="disconnected",
                max_length=32,
            ),
        ),
    ]
