from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scale", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scalebridgereading",
            name="device_id",
            field=models.CharField(db_index=True, max_length=100),
        ),
        migrations.AddConstraint(
            model_name="scalebridgereading",
            constraint=models.UniqueConstraint(
                fields=("device_id", "workstation_id"),
                name="scale_bridge_device_workstation_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="scalebridgereading",
            index=models.Index(
                fields=("device_id", "workstation_id"),
                name="scale_bridge_device_ws_idx",
            ),
        ),
    ]
