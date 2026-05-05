# Generated manually to backfill store department stock from existing item balances.

from django.db import migrations


def backfill_store_department_stock(apps, schema_editor):
    Item = apps.get_model("Items", "Item")
    DepartmentStock = apps.get_model("blending", "DepartmentStock")

    department_stock_rows = []
    for item in Item.objects.all().only("id", "current_stock"):
        department_stock_rows.append(
            DepartmentStock(
                item_id=item.id,
                department="STORE",
                quantity=item.current_stock,
            )
        )

    DepartmentStock.objects.bulk_create(department_stock_rows, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("Items", "0002_item_stock"),
        ("blending", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_store_department_stock, migrations.RunPython.noop),
    ]
