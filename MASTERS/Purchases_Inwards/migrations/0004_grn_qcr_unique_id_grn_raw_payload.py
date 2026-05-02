# Generated manually for GRN receiver idempotency support.

import random

import Purchases_Inwards.models
from django.db import migrations, models
from django.db.models import Q


def build_wpe_unique_id(used_ids):
    while True:
        value = f"WPE-{random.SystemRandom().randrange(100000000):08d}"
        if value not in used_ids:
            used_ids.add(value)
            return value


def populate_unique_ids(apps, schema_editor):
    for model_name in ("GRN", "QCR"):
        model = apps.get_model("Purchases_Inwards", model_name)
        used_ids = set(
            model.objects.exclude(unique_id__isnull=True)
            .exclude(unique_id="")
            .values_list("unique_id", flat=True)
        )

        for instance in model.objects.filter(Q(unique_id__isnull=True) | Q(unique_id="")):
            instance.unique_id = build_wpe_unique_id(used_ids)
            instance.save(update_fields=["unique_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("Purchases_Inwards", "0003_grn_moved_to_qcr_at_grn_moved_to_qcr_by_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="grn",
            name="unique_id",
            field=models.CharField(blank=True, editable=False, max_length=12, null=True),
        ),
        migrations.AddField(
            model_name="qcr",
            name="unique_id",
            field=models.CharField(blank=True, editable=False, max_length=12, null=True),
        ),
        migrations.AddField(
            model_name="grn",
            name="raw_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(populate_unique_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="grn",
            name="unique_id",
            field=models.CharField(
                default=Purchases_Inwards.models.generate_wpe_unique_id,
                editable=False,
                max_length=12,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="qcr",
            name="unique_id",
            field=models.CharField(
                default=Purchases_Inwards.models.generate_wpe_unique_id,
                editable=False,
                max_length=12,
                unique=True,
            ),
        ),
    ]
