import hashlib
from django.core.management.base import BaseCommand
from apps.production.models import ProductionMachine, BOMVariant, BOMVariantComponent
from apps.items.models import Item


class Command(BaseCommand):
    help = "Seed production machines and recipe definitions"

    def handle(self, *args, **options):
        machines_data = [
            {"machine_code": "HSM-500-1", "name": "HSM 500 - Unit 1", "machine_type": "HIGH_SPEED_MIX", "applicable_stages": "AD,BL", "location": "Blending Floor"},
            {"machine_code": "HSM-500-2", "name": "HSM 500 - Unit 2", "machine_type": "HIGH_SPEED_MIX", "applicable_stages": "AD,BL", "location": "Blending Floor"},
            {"machine_code": "GRAN-WPE-1", "name": "Granulator WPE Blend", "machine_type": "GRANULATOR", "applicable_stages": "GL", "location": "Granulation Bay"},
        ]
        for md in machines_data:
            m, created = ProductionMachine.objects.get_or_create(machine_code=md["machine_code"], defaults=md)
            self.stdout.write(f"{'Created' if created else 'Exists'}: {m.machine_code}")

        items = list(Item.objects.filter(status=True)[:4])
        if len(items) >= 2:
            password_hash = hashlib.sha256("9512".encode()).hexdigest()
            bom, created = BOMVariant.objects.get_or_create(
                variant_code="BOM-GL-001",
                defaults={
                    "name": "Granulated Blend Type A",
                    "revision": "v1",
                    "is_active": True,
                    "access_password_hash": password_hash,
                    "notes": "Standard additive blend recipe",
                }
            )
            if created:
                recipes = [
                    (500, 490, 510, False),
                    (250, 240, 260, False),
                    (100, 95, 105, False),
                    (150, 140, 160, True),
                ]
                for i, (item, (target, mn, mx, is_regrind)) in enumerate(zip(items[:4], recipes)):
                    BOMVariantComponent.objects.create(
                        bom_variant=bom, item=item,
                        target_weight_grams=target, min_weight_grams=mn, max_weight_grams=mx,
                        sequence=i + 1, is_regrind=is_regrind,
                    )
                self.stdout.write(f"Created BOM {bom.variant_code} with {len(items[:4])} components")
            else:
                self.stdout.write(f"BOM exists: {bom.variant_code}")
        else:
            self.stdout.write("Not enough active items. Add items first.")

        self.stdout.write(self.style.SUCCESS("Production seed complete."))
