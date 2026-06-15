from django.db import migrations


def ensure_blend_production_type(apps, schema_editor):
    ProductionTypeMaster = apps.get_model("wpe_masters", "ProductionTypeMaster")
    ProductionTypeMaster.objects.get_or_create(name="WPE Blend Production", defaults={"is_active": True})


class Migration(migrations.Migration):
    dependencies = [
        ("wpe_masters", "0008_serialportconfigurationmaster_printermaster_and_more"),
    ]

    operations = [
        migrations.RunPython(ensure_blend_production_type, migrations.RunPython.noop),
    ]
