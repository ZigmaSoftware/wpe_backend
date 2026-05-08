from decimal import Decimal

import uuid

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


STOCK_ZERO = Decimal("0.000")


def forward_refactor_store_workflow(apps, schema_editor):
    Warehouse = apps.get_model("store", "Warehouse")
    StoreStock = apps.get_model("store", "StoreStock")
    StoreTransaction = apps.get_model("store", "StoreTransaction")
    StockRequest = apps.get_model("store", "StockRequest")
    StockRequestItem = apps.get_model("store", "StockRequestItem")
    BlendingStock = apps.get_model("blending", "BlendingStock")

    store_warehouse, _ = Warehouse.objects.get_or_create(
        code="STORE",
        defaults={
            "name": "Main Store",
            "warehouse_type": "STORE",
            "description": "System warehouse for store inventory",
            "is_active": True,
            "is_system": True,
        },
    )
    blending_warehouse, _ = Warehouse.objects.get_or_create(
        code="BLENDING",
        defaults={
            "name": "Blending Floor",
            "warehouse_type": "BLENDING",
            "description": "System warehouse for blending inventory",
            "is_active": True,
            "is_system": True,
        },
    )

    StoreStock.objects.filter(warehouse__isnull=True).update(
        warehouse_id=store_warehouse.id,
        reserved_qty=STOCK_ZERO,
    )

    existing_pairs = set(StoreStock.objects.values_list("item_id", "warehouse_id"))
    blending_rows = []
    for legacy_blending_stock in BlendingStock.objects.all().only("item_id", "quantity", "created_at", "updated_at"):
        pair = (legacy_blending_stock.item_id, blending_warehouse.id)
        if pair in existing_pairs:
            continue
        blending_rows.append(
            StoreStock(
                item_id=legacy_blending_stock.item_id,
                warehouse_id=blending_warehouse.id,
                available_qty=legacy_blending_stock.quantity,
                reserved_qty=STOCK_ZERO,
                created_at=legacy_blending_stock.created_at,
                updated_at=legacy_blending_stock.updated_at,
            )
        )
        existing_pairs.add(pair)
    if blending_rows:
        StoreStock.objects.bulk_create(blending_rows)

    for stock_request in StockRequest.objects.order_by("id"):
        updated_fields = []
        if not stock_request.request_no:
            stock_request.request_no = f"SR-{stock_request.id:08d}"
            updated_fields.append("request_no")
        if stock_request.requesting_warehouse_id is None:
            stock_request.requesting_warehouse_id = blending_warehouse.id
            updated_fields.append("requesting_warehouse")
        if stock_request.issuing_warehouse_id is None:
            stock_request.issuing_warehouse_id = store_warehouse.id
            updated_fields.append("issuing_warehouse")
        if updated_fields:
            stock_request.save(update_fields=updated_fields)

        if not StockRequestItem.objects.filter(stock_request_id=stock_request.id, item_id=stock_request.item_id).exists():
            approved_qty = stock_request.quantity if stock_request.status == "APPROVED" else STOCK_ZERO
            StockRequestItem.objects.create(
                stock_request_id=stock_request.id,
                item_id=stock_request.item_id,
                requested_qty=stock_request.quantity,
                approved_qty=approved_qty,
                issued_qty=approved_qty,
            )

    running_balance_by_item_warehouse: dict[tuple[int, int], Decimal] = {}
    for transaction_row in StoreTransaction.objects.order_by("created_at", "id"):
        if transaction_row.warehouse_id is None:
            transaction_row.warehouse_id = store_warehouse.id

        if not transaction_row.transaction_no:
            transaction_row.transaction_no = f"STX-{transaction_row.id:08d}"

        if transaction_row.transaction_date is None:
            transaction_row.transaction_date = (
                transaction_row.created_at.date() if transaction_row.created_at else django.utils.timezone.localdate()
            )

        if transaction_row.transaction_type == "GRN_IN":
            transaction_row.transaction_type = "GRN_INWARD"
            transaction_row.reference_type = "GRN"
            outward_qty = STOCK_ZERO
        elif transaction_row.transaction_type == "TRANSFER_OUT":
            transaction_row.transaction_type = "SR_ISSUE"
            transaction_row.reference_type = "STORE_REQUEST"
            outward_qty = transaction_row.inward_qty
            transaction_row.inward_qty = STOCK_ZERO
        else:
            transaction_row.transaction_type = "ADJUSTMENT_IN"
            transaction_row.reference_type = "ADJUSTMENT"
            outward_qty = STOCK_ZERO

        transaction_row.outward_qty = outward_qty
        running_key = (transaction_row.item_id, transaction_row.warehouse_id)
        previous_balance = running_balance_by_item_warehouse.get(running_key, STOCK_ZERO)
        current_balance = previous_balance + transaction_row.inward_qty - transaction_row.outward_qty
        transaction_row.balance_qty = current_balance if current_balance > STOCK_ZERO else STOCK_ZERO
        running_balance_by_item_warehouse[running_key] = transaction_row.balance_qty

        transaction_row.save(
            update_fields=[
                "warehouse",
                "transaction_no",
                "transaction_date",
                "transaction_type",
                "reference_type",
                "inward_qty",
                "outward_qty",
                "balance_qty",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("blending", "0003_refactor_blending_stock"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("store", "0002_backfill_store_stock"),
    ]

    operations = [
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(db_index=True, max_length=30, unique=True)),
                ("name", models.CharField(db_index=True, max_length=120)),
                (
                    "warehouse_type",
                    models.CharField(
                        choices=[("STORE", "Store"), ("BLENDING", "Blending"), ("GENERAL", "General")],
                        db_index=True,
                        default="GENERAL",
                        max_length=20,
                    ),
                ),
                ("description", models.TextField(blank=True, null=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("is_system", models.BooleanField(default=False)),
            ],
            options={
                "ordering": ["name", "id"],
            },
        ),
        migrations.AlterModelOptions(
            name="storestock",
            options={"ordering": ["warehouse__name", "item__item_name", "id"]},
        ),
        migrations.AlterModelOptions(
            name="storetransaction",
            options={"ordering": ["-transaction_date", "-created_at", "-id"]},
        ),
        migrations.RemoveConstraint(
            model_name="storestock",
            name="store_stock_quantity_gte_zero",
        ),
        migrations.AlterField(
            model_name="storestock",
            name="item",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inventory_stocks", to="Items.item"),
        ),
        migrations.RenameField(
            model_name="storestock",
            old_name="quantity",
            new_name="available_qty",
        ),
        migrations.AddField(
            model_name="storestock",
            name="reserved_qty",
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal("0.000"),
                max_digits=14,
                validators=[django.core.validators.MinValueValidator(Decimal("0.000"))],
            ),
        ),
        migrations.AddField(
            model_name="storestock",
            name="warehouse",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="current_stocks",
                to="store.warehouse",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="storetransaction",
            name="store_tx_quantity_gt_zero",
        ),
        migrations.RemoveConstraint(
            model_name="storetransaction",
            name="store_tx_type_reference_unique",
        ),
        migrations.RemoveIndex(
            model_name="storetransaction",
            name="store_tx_item_type_idx",
        ),
        migrations.RemoveIndex(
            model_name="storetransaction",
            name="store_tx_reference_idx",
        ),
        migrations.RemoveIndex(
            model_name="storetransaction",
            name="store_tx_created_idx",
        ),
        migrations.RenameField(
            model_name="storetransaction",
            old_name="quantity",
            new_name="inward_qty",
        ),
        migrations.AddField(
            model_name="storetransaction",
            name="balance_qty",
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal("0.000"),
                max_digits=14,
                validators=[django.core.validators.MinValueValidator(Decimal("0.000"))],
            ),
        ),
        migrations.AddField(
            model_name="storetransaction",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_store_transactions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="storetransaction",
            name="outward_qty",
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal("0.000"),
                max_digits=14,
                validators=[django.core.validators.MinValueValidator(Decimal("0.000"))],
            ),
        ),
        migrations.AddField(
            model_name="storetransaction",
            name="reference_type",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name="storetransaction",
            name="remarks",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="storetransaction",
            name="transaction_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="storetransaction",
            name="transaction_no",
            field=models.CharField(blank=True, db_index=True, max_length=30, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="storetransaction",
            name="warehouse",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="stock_transactions",
                to="store.warehouse",
            ),
        ),
        migrations.AlterField(
            model_name="storetransaction",
            name="reference_id",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.RenameField(
            model_name="stockrequest",
            old_name="approved_at",
            new_name="action_at",
        ),
        migrations.RenameField(
            model_name="stockrequest",
            old_name="approved_by",
            new_name="action_by",
        ),
        migrations.RemoveConstraint(
            model_name="stockrequest",
            name="store_request_quantity_gt_zero",
        ),
        migrations.RemoveIndex(
            model_name="stockrequest",
            name="store_request_item_status_idx",
        ),
        migrations.RemoveIndex(
            model_name="stockrequest",
            name="store_request_created_idx",
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="approval_remarks",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="cancelled_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cancelled_store_stock_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="issuing_warehouse",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="issued_store_requests",
                to="store.warehouse",
            ),
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="remarks",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="request_no",
            field=models.CharField(blank=True, db_index=True, max_length=30, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="stockrequest",
            name="requesting_warehouse",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="requested_store_requests",
                to="store.warehouse",
            ),
        ),
        migrations.CreateModel(
            name="StockRequestItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unique_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "requested_qty",
                    models.DecimalField(
                        decimal_places=3,
                        max_digits=14,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.001"))],
                    ),
                ),
                (
                    "approved_qty",
                    models.DecimalField(
                        decimal_places=3,
                        default=Decimal("0.000"),
                        max_digits=14,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.000"))],
                    ),
                ),
                (
                    "issued_qty",
                    models.DecimalField(
                        decimal_places=3,
                        default=Decimal("0.000"),
                        max_digits=14,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.000"))],
                    ),
                ),
                ("remarks", models.TextField(blank=True, null=True)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="store_request_items",
                        to="Items.item",
                    ),
                ),
                (
                    "stock_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="store.stockrequest",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.RunPython(forward_refactor_store_workflow, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="stockrequest",
            name="item",
        ),
        migrations.RemoveField(
            model_name="stockrequest",
            name="quantity",
        ),
        migrations.AlterField(
            model_name="stockrequest",
            name="action_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="actioned_store_stock_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="stockrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("APPROVED", "Approved"),
                    ("REJECTED", "Rejected"),
                    ("PARTIALLY_APPROVED", "Partially Approved"),
                    ("CANCELLED", "Cancelled"),
                ],
                db_index=True,
                default="PENDING",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="storestock",
            name="warehouse",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="current_stocks",
                to="store.warehouse",
            ),
        ),
        migrations.AlterField(
            model_name="storetransaction",
            name="item",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="store_transactions", to="Items.item"),
        ),
        migrations.AlterField(
            model_name="storetransaction",
            name="inward_qty",
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal("0.000"),
                max_digits=14,
                validators=[django.core.validators.MinValueValidator(Decimal("0.000"))],
            ),
        ),
        migrations.AlterField(
            model_name="storetransaction",
            name="reference_type",
            field=models.CharField(
                choices=[
                    ("GRN", "GRN"),
                    ("OPENING_STOCK", "Opening Stock"),
                    ("MANUAL", "Manual"),
                    ("ADJUSTMENT", "Adjustment"),
                    ("STORE_REQUEST", "Store Request"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="storetransaction",
            name="transaction_date",
            field=models.DateField(db_index=True, default=django.utils.timezone.localdate),
        ),
        migrations.AlterField(
            model_name="storetransaction",
            name="transaction_type",
            field=models.CharField(
                choices=[
                    ("GRN_INWARD", "GRN Inward"),
                    ("OPENING_STOCK", "Opening Stock"),
                    ("MANUAL_INWARD", "Manual Inward"),
                    ("MANUAL_OUTWARD", "Manual Outward"),
                    ("ADJUSTMENT_IN", "Adjustment In"),
                    ("ADJUSTMENT_OUT", "Adjustment Out"),
                    ("SR_ISSUE", "Store Request Issue"),
                    ("SR_RECEIPT", "Store Request Receipt"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="storetransaction",
            name="warehouse",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="stock_transactions",
                to="store.warehouse",
            ),
        ),
        migrations.AddConstraint(
            model_name="storestock",
            constraint=models.CheckConstraint(
                condition=models.Q(("available_qty__gte", Decimal("0.000"))),
                name="store_stock_available_qty_gte_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="storestock",
            constraint=models.CheckConstraint(
                condition=models.Q(("reserved_qty__gte", Decimal("0.000"))),
                name="store_stock_reserved_qty_gte_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="storestock",
            constraint=models.UniqueConstraint(fields=("item", "warehouse"), name="store_stock_item_warehouse_unique"),
        ),
        migrations.AddIndex(
            model_name="storestock",
            index=models.Index(fields=["warehouse", "item"], name="store_stock_wh_item_idx"),
        ),
        migrations.AddIndex(
            model_name="storestock",
            index=models.Index(fields=["item", "warehouse"], name="store_stock_item_wh_idx"),
        ),
        migrations.AddConstraint(
            model_name="storetransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(("inward_qty__gte", Decimal("0.000"))),
                name="store_tx_inward_qty_gte_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="storetransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(("outward_qty__gte", Decimal("0.000"))),
                name="store_tx_outward_qty_gte_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="storetransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(("balance_qty__gte", Decimal("0.000"))),
                name="store_tx_balance_qty_gte_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="storetransaction",
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(("inward_qty", Decimal("0.000"))) & models.Q(("outward_qty__gt", Decimal("0.000"))))
                    | (models.Q(("inward_qty__gt", Decimal("0.000"))) & models.Q(("outward_qty", Decimal("0.000"))))
                ),
                name="store_tx_single_direction_qty",
            ),
        ),
        migrations.AddIndex(
            model_name="storetransaction",
            index=models.Index(fields=["warehouse", "item", "transaction_date"], name="store_tx_wh_item_date_idx"),
        ),
        migrations.AddIndex(
            model_name="storetransaction",
            index=models.Index(fields=["transaction_type", "reference_id"], name="store_tx_type_ref_idx"),
        ),
        migrations.AddIndex(
            model_name="storetransaction",
            index=models.Index(fields=["reference_type", "reference_id"], name="store_tx_ref_type_ref_idx"),
        ),
        migrations.AddConstraint(
            model_name="stockrequestitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("requested_qty__gt", Decimal("0.000"))),
                name="stock_request_item_requested_qty_gt_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockrequestitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("approved_qty__gte", Decimal("0.000"))),
                name="stock_request_item_approved_qty_gte_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockrequestitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("issued_qty__gte", Decimal("0.000"))),
                name="stock_request_item_issued_qty_gte_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockrequestitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("approved_qty__lte", models.F("requested_qty"))),
                name="stock_request_item_approved_lte_requested",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockrequestitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("issued_qty__lte", models.F("approved_qty"))),
                name="stock_request_item_issued_lte_approved",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockrequestitem",
            constraint=models.UniqueConstraint(
                fields=("stock_request", "item"),
                name="stock_request_item_unique_item_per_request",
            ),
        ),
        migrations.AddIndex(
            model_name="stockrequestitem",
            index=models.Index(fields=["stock_request", "item"], name="sr_item_req_idx"),
        ),
        migrations.AddIndex(
            model_name="stockrequest",
            index=models.Index(fields=["status", "requested_at"], name="store_request_status_date_idx"),
        ),
        migrations.AddIndex(
            model_name="stockrequest",
            index=models.Index(fields=["request_no"], name="store_request_no_idx"),
        ),
    ]
