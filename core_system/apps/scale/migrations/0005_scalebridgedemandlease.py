from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scale", "0004_bridge_client_identity"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScaleBridgeDemandLease",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("workstation_id", models.CharField(db_index=True, max_length=100)),
                ("bridge_client_id", models.CharField(db_index=True, max_length=128)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["workstation_id", "bridge_client_id", "expires_at"],
                        name="scale_dem_ws_cli_exp_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("workstation_id", "bridge_client_id"),
                        name="scale_bridge_demand_ws_client_unique",
                    ),
                ],
            },
        ),
    ]
