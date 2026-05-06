from django.db import migrations


def backfill_store_stock(apps, schema_editor):
    Item = apps.get_model("Items", "Item")
    DepartmentStock = apps.get_model("blending", "DepartmentStock")
    StoreStock = apps.get_model("store", "StoreStock")

    existing_item_ids: set[int] = set()
    store_stock_rows = []

    for legacy_stock in DepartmentStock.objects.filter(department="STORE").only("item_id", "quantity"):
        store_stock_rows.append(
            StoreStock(
                item_id=legacy_stock.item_id,
                quantity=legacy_stock.quantity,
            )
        )
        existing_item_ids.add(legacy_stock.item_id)

    for item in Item.objects.exclude(id__in=existing_item_ids).only("id", "current_stock"):
        store_stock_rows.append(
            StoreStock(
                item_id=item.id,
                quantity=item.current_stock,
            )
        )

    StoreStock.objects.bulk_create(store_stock_rows, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("Items", "0002_item_stock"),
        ("blending", "0002_backfill_store_stock"),
        ("store", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_store_stock, migrations.RunPython.noop),
    ]

