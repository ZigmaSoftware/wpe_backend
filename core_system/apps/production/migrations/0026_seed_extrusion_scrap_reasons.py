from django.db import migrations


# Scrap Categories and Reason Master — FRD Extrusion_Scrap_Packing_KPI_FRD_V1_0, section 7.
SCRAP_CATEGORY_REASONS = (
    ("Straightness Failure", ["Profile bend, twist or straightness outside limit."]),
    ("Flatness Failure", ["Surface or profile flatness outside approved tolerance."]),
    ("Section Weight Variation", ["Section weight below or above allowed standard."]),
    ("Length Variation", ["Cut length shorter or longer than specification."]),
    ("Surface / Visual Defect", ["Scratch, dent, mark, blister, crack or finish issue."]),
    ("Dimensional Defect", ["Critical dimension outside approved drawing tolerance."]),
    ("Handling Damage", ["Damage caused during transfer, stacking or packing."]),
    ("Packing Rejection", ["Packing quality, consumable or packet arrangement issue."]),
    ("Weight Deviation", ["Packet remains underweight or overweight after correction decision."]),
    ("Other", ["Any approved reason not covered above — remarks mandatory."]),
)


def seed_scrap_reasons(apps, schema_editor):
    ScrapCategory = apps.get_model("production", "ScrapCategory")
    ScrapReason = apps.get_model("production", "ScrapReason")

    for category_index, (category_name, reasons) in enumerate(SCRAP_CATEGORY_REASONS, start=1):
        category, _ = ScrapCategory.objects.get_or_create(
            name=category_name,
            defaults={"code": f"SCRC{category_index:02d}", "is_active": True},
        )
        for reason_index, reason_text in enumerate(reasons, start=1):
            ScrapReason.objects.get_or_create(
                category=category,
                name=reason_text,
                defaults={"code": f"SCRR{category_index:02d}{reason_index:02d}", "is_active": True},
            )


def unseed_scrap_reasons(apps, schema_editor):
    ScrapCategory = apps.get_model("production", "ScrapCategory")
    category_names = [name for name, _ in SCRAP_CATEGORY_REASONS]
    ScrapCategory.objects.filter(name__in=category_names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0025_extrusion_module"),
    ]

    operations = [
        migrations.RunPython(seed_scrap_reasons, unseed_scrap_reasons),
    ]
