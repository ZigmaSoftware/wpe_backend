from __future__ import annotations

from decimal import Decimal
import re
from django.db import models
from django.db.models import Q

from apps.production.models import (
    BatchWeightEntry,
    ProductionBatch,
    ProductionOrder,
    ProductionOutputCapture,
)

from .models import ProductionInventoryTransaction

ZERO = Decimal("0.000")


def _resolve_work_center_name(order: ProductionOrder) -> str:
    extra = order.extra_form_data or {}
    raw_name = str(extra.get("work_center_name") or "").strip()
    if raw_name:
        return raw_name
    raw_value = str(extra.get("work_center") or "").strip()
    return raw_value


def _resolve_line_label(order: ProductionOrder) -> str:
    line_name = str(order.line_name or "").strip()
    line_number = str(order.line_number or "").strip()
    if line_number and line_name:
        return f"{line_number} - {line_name}"
    return line_name or line_number


def _resolve_production_item_fields(order: ProductionOrder) -> tuple[str, str]:
    production_code = str(order.production_id or "").strip()
    production_name = str(order.production_for or "").strip() or str(order.production_type or "").strip() or production_code
    return production_code, production_name


def _extract_workflow_suffix(value: str | None) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    match = re.search(r"(-\d+)$", text)
    if match:
        return match.group(1)
    return text


def _consume_stage_quantity(
    *,
    stage: str,
    next_stage: str,
    quantity: Decimal,
    production_order: ProductionOrder,
    source_batch: ProductionBatch | None,
    lineage_batch_code: str | None = None,
):
    if quantity <= ZERO:
        return

    if source_batch is None:
        source_rows = []
    else:
        source_rows = list(
            ProductionInventoryTransaction.objects.select_for_update().filter(
                stage=stage,
                source_batch=source_batch,
                balance_qty__gt=ZERO,
            ).order_by("created_at", "id")
        )

    if not source_rows:
        lineage_suffix = _extract_workflow_suffix(lineage_batch_code or getattr(source_batch, "batch_no", None))
        if lineage_suffix:
            source_rows = list(
                ProductionInventoryTransaction.objects.select_for_update().filter(
                    stage=stage,
                    production_order=production_order,
                    balance_qty__gt=ZERO,
                ).filter(
                    Q(batch_code__iendswith=lineage_suffix) | Q(reference_no__iendswith=lineage_suffix)
                ).order_by("created_at", "id")
            )

    if not source_rows:
        return

    for row in source_rows:
        row.outward_qty = Decimal(str(row.inward_qty or ZERO))
        row.balance_qty = ZERO
        row.to_stage = next_stage
        row.status = ProductionInventoryTransaction.Status.COMPLETED
        row.save(update_fields=["outward_qty", "balance_qty", "to_stage", "status", "updated_at"])


def get_available_stage_quantity(production_order: ProductionOrder, stage: str) -> Decimal:
    total = ProductionInventoryTransaction.objects.filter(
        production_order=production_order,
        stage=stage,
        balance_qty__gt=ZERO,
    ).aggregate(total=models.Sum("balance_qty"))
    return Decimal(str(total.get("total") or ZERO))


def upsert_inventory_transaction(
    *,
    movement_key: str,
    stage: str,
    batch_code: str,
    production_order: ProductionOrder,
    source_batch: ProductionBatch | None = None,
    output_capture: ProductionOutputCapture | None = None,
    item=None,
    item_code: str = "",
    item_name: str = "",
    quantity: Decimal | str | int | float = ZERO,
    inward_qty: Decimal | str | int | float | None = None,
    outward_qty: Decimal | str | int | float | None = None,
    balance_qty: Decimal | str | int | float | None = None,
    from_stage: str = "",
    to_stage: str = "",
    reference_no: str | None = None,
    scan_code: str | None = None,
    work_center: str | None = None,
    line: str | None = None,
    status: str = ProductionInventoryTransaction.Status.IN_PROGRESS,
    created_by=None,
) -> ProductionInventoryTransaction:
    quantity_decimal = Decimal(str(quantity or ZERO))
    resolved_inward_qty = Decimal(str(inward_qty if inward_qty is not None else quantity_decimal))
    resolved_outward_qty = Decimal(str(outward_qty if outward_qty is not None else ZERO))
    resolved_balance_qty = Decimal(str(balance_qty if balance_qty is not None else quantity_decimal))

    defaults = {
        "stage": stage,
        "batch_code": batch_code,
        "production_order": production_order,
        "production_id": str(production_order.production_id or "").strip(),
        "production_type": str(production_order.production_type or "").strip(),
        "source_batch": source_batch,
        "output_capture": output_capture,
        "item": item,
        "item_code": item_code or getattr(item, "item_code", "") or "",
        "item_name": item_name or getattr(item, "item_name", "") or "",
        "inward_qty": resolved_inward_qty,
        "outward_qty": resolved_outward_qty,
        "balance_qty": resolved_balance_qty,
        "uom": getattr(item, "unit", "") or "",
        "from_stage": from_stage,
        "to_stage": to_stage,
        "reference_no": reference_no or str(production_order.production_id or "").strip() or None,
        "scan_code": scan_code or None,
        "work_center": work_center if work_center is not None else _resolve_work_center_name(production_order) or None,
        "line": line if line is not None else _resolve_line_label(production_order) or None,
        "status": status,
        "created_by": created_by,
    }
    row, _created = ProductionInventoryTransaction.objects.update_or_create(
        movement_key=movement_key,
        defaults=defaults,
    )
    return row


def _iter_batch_weight_entries(batch: ProductionBatch):
    return (
        batch.weight_entries.select_related("item", "bom_component__item")
        .order_by("bom_component__sequence", "id")
    )


def sync_ad_save_weight(entry: BatchWeightEntry, *, created_by=None) -> ProductionInventoryTransaction | None:
    if entry.batch.stage != ProductionBatch.Stage.AD or entry.entered_weight_grams is None:
        return None

    item = entry.item or getattr(entry.bom_component, "item", None)
    if item is None:
        return None

    quantity = Decimal(str(entry.entered_weight_grams or ZERO))
    return upsert_inventory_transaction(
        movement_key=f"ad-save:{entry.id}",
        stage=ProductionInventoryTransaction.Stage.ADDITIVE_WORK_CENTER,
        batch_code=str(entry.batch.batch_no or "").strip(),
        production_order=entry.batch.production_order,
        source_batch=entry.batch,
        item=item,
        quantity=quantity,
        inward_qty=quantity,
        outward_qty=ZERO,
        balance_qty=quantity,
        from_stage="AD",
        to_stage=ProductionInventoryTransaction.Stage.ADDITIVE_WORK_CENTER,
        reference_no=str(entry.batch.production_order.production_id or "").strip() or None,
        status=ProductionInventoryTransaction.Status.IN_PROGRESS,
        created_by=created_by,
    )


def move_ad_batch_to_blend_wip(ad_batch: ProductionBatch, *, created_by=None) -> list[ProductionInventoryTransaction]:
    moved_rows: list[ProductionInventoryTransaction] = []
    for entry in _iter_batch_weight_entries(ad_batch):
        if entry.entered_weight_grams is None:
            continue
        item = entry.item or getattr(entry.bom_component, "item", None)
        if item is None:
            continue

        quantity = Decimal(str(entry.entered_weight_grams or ZERO))
        upsert_inventory_transaction(
            movement_key=f"ad-save:{entry.id}",
            stage=ProductionInventoryTransaction.Stage.ADDITIVE_WORK_CENTER,
            batch_code=str(ad_batch.batch_no or "").strip(),
            production_order=ad_batch.production_order,
            source_batch=ad_batch,
            item=item,
            quantity=quantity,
            inward_qty=quantity,
            outward_qty=quantity,
            balance_qty=ZERO,
            from_stage="AD",
            to_stage=ProductionInventoryTransaction.Stage.BLEND_WIP,
            reference_no=str(ad_batch.production_order.production_id or "").strip() or None,
            status=ProductionInventoryTransaction.Status.COMPLETED,
            created_by=created_by,
        )
        moved_rows.append(
            upsert_inventory_transaction(
                movement_key=f"ad-final:blend-wip:{entry.id}",
                stage=ProductionInventoryTransaction.Stage.BLEND_WIP,
                batch_code=str(ad_batch.batch_no or "").strip(),
                production_order=ad_batch.production_order,
                source_batch=ad_batch,
                item=item,
                quantity=quantity,
                inward_qty=quantity,
                outward_qty=ZERO,
                balance_qty=quantity,
                from_stage=ProductionInventoryTransaction.Stage.ADDITIVE_WORK_CENTER,
                to_stage=ProductionInventoryTransaction.Stage.BLEND_WIP,
                reference_no=str(ad_batch.batch_no or "").strip() or None,
                status=ProductionInventoryTransaction.Status.IN_PROGRESS,
                created_by=created_by,
            )
        )
    return moved_rows


def record_bl_final_capture(bl_batch: ProductionBatch, output_capture: ProductionOutputCapture, *, created_by=None) -> ProductionInventoryTransaction:
    production_code, production_name = _resolve_production_item_fields(bl_batch.production_order)
    quantity = Decimal(str(output_capture.weight_kg or ZERO))

    source_batch = getattr(bl_batch, "parent_batch", None)
    _consume_stage_quantity(
        stage=ProductionInventoryTransaction.Stage.BLEND_WIP,
        next_stage=ProductionInventoryTransaction.Stage.BLEND_STORE,
        quantity=quantity,
        production_order=bl_batch.production_order,
        source_batch=source_batch,
        lineage_batch_code=str(bl_batch.batch_no or "").strip() or None,
    )

    return upsert_inventory_transaction(
        movement_key=f"bl-final:blend-store:{output_capture.id}",
        stage=ProductionInventoryTransaction.Stage.BLEND_STORE,
        batch_code=str(bl_batch.batch_no or "").strip(),
        production_order=bl_batch.production_order,
        source_batch=bl_batch,
        output_capture=output_capture,
        item=None,
        item_code=production_code,
        item_name=production_name,
        quantity=quantity,
        inward_qty=quantity,
        outward_qty=ZERO,
        balance_qty=quantity,
        from_stage=ProductionInventoryTransaction.Stage.BLENDING_WORK_CENTER,
        to_stage=ProductionInventoryTransaction.Stage.BLEND_STORE,
        reference_no=str(bl_batch.batch_no or "").strip() or None,
        scan_code=str(output_capture.binlot or output_capture.scancode_id or "").strip() or None,
        status=ProductionInventoryTransaction.Status.IN_PROGRESS,
        created_by=created_by,
    )


def move_bl_batch_to_granulation_work_center(
    bl_batch: ProductionBatch,
    output_capture: ProductionOutputCapture | None = None,
    *,
    created_by=None,
) -> list[ProductionInventoryTransaction]:
    moved_rows: list[ProductionInventoryTransaction] = []
    blend_store_rows = list(
        ProductionInventoryTransaction.objects.filter(
            stage=ProductionInventoryTransaction.Stage.BLEND_STORE,
            source_batch=bl_batch,
            balance_qty__gt=ZERO,
        ).select_related("item", "production_order", "source_batch")
    )

    for row in blend_store_rows:
        row.outward_qty = row.inward_qty
        row.balance_qty = ZERO
        row.to_stage = ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER
        row.status = ProductionInventoryTransaction.Status.COMPLETED
        row.save(update_fields=["outward_qty", "balance_qty", "to_stage", "status", "updated_at"])

        moved_rows.append(
            upsert_inventory_transaction(
                movement_key=f"bl-out:gran-work-center:{row.id}",
                stage=ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER,
                batch_code="",
                production_order=bl_batch.production_order,
                source_batch=bl_batch,
                output_capture=output_capture,
                item=row.item,
                item_code=row.item_code,
                item_name=row.item_name,
                quantity=row.inward_qty,
                inward_qty=row.inward_qty,
                outward_qty=ZERO,
                balance_qty=row.inward_qty,
                from_stage=ProductionInventoryTransaction.Stage.BLEND_STORE,
                to_stage=ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER,
                reference_no=str(bl_batch.batch_no or "").strip() or None,
                scan_code=output_capture.scancode_id if output_capture else None,
                status=ProductionInventoryTransaction.Status.IN_PROGRESS,
                created_by=created_by,
            )
        )
    return moved_rows


def record_gl_final_capture(gl_batch: ProductionBatch, output_capture: ProductionOutputCapture, *, created_by=None) -> ProductionInventoryTransaction:
    production_code, production_name = _resolve_production_item_fields(gl_batch.production_order)
    quantity = Decimal(str(output_capture.weight_kg or ZERO))

    _consume_stage_quantity(
        stage=ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER,
        next_stage=ProductionInventoryTransaction.Stage.GRANULATION_STORE,
        quantity=quantity,
        production_order=gl_batch.production_order,
        source_batch=getattr(gl_batch, "parent_batch", None),
        lineage_batch_code=str(gl_batch.batch_no or "").strip() or None,
    )

    return upsert_inventory_transaction(
        movement_key=f"gl-final:granulation-store:{output_capture.id}",
        stage=ProductionInventoryTransaction.Stage.GRANULATION_STORE,
        batch_code=str(gl_batch.batch_no or "").strip(),
        production_order=gl_batch.production_order,
        source_batch=gl_batch,
        output_capture=output_capture,
        item=None,
        item_code=production_code,
        item_name=production_name,
        quantity=quantity,
        inward_qty=quantity,
        outward_qty=ZERO,
        balance_qty=quantity,
        from_stage=ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER,
        to_stage=ProductionInventoryTransaction.Stage.GRANULATION_STORE,
        reference_no=str(gl_batch.batch_no or "").strip() or None,
        scan_code=str(output_capture.binlot or output_capture.scancode_id or "").strip() or None,
        status=ProductionInventoryTransaction.Status.IN_PROGRESS,
        created_by=created_by,
    )


def move_gl_batch_to_connection_line(gl_batch: ProductionBatch, output_capture: ProductionOutputCapture | None = None, *, created_by=None) -> list[ProductionInventoryTransaction]:
    moved_rows: list[ProductionInventoryTransaction] = []
    gran_store_rows = list(
        ProductionInventoryTransaction.objects.filter(
            stage=ProductionInventoryTransaction.Stage.GRANULATION_STORE,
            source_batch=gl_batch,
            balance_qty__gt=ZERO,
        ).select_related("item", "production_order", "source_batch")
    )

    for row in gran_store_rows:
        row.outward_qty = row.inward_qty
        row.balance_qty = ZERO
        row.to_stage = ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE
        row.status = ProductionInventoryTransaction.Status.COMPLETED
        row.save(update_fields=["outward_qty", "balance_qty", "to_stage", "status", "updated_at"])

        moved_rows.append(
            upsert_inventory_transaction(
                movement_key=f"gl-out:connection-line:{row.id}",
                stage=ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
                batch_code="",
                production_order=gl_batch.production_order,
                source_batch=gl_batch,
                output_capture=output_capture,
                item=row.item,
                item_code=row.item_code,
                item_name=row.item_name,
                quantity=row.inward_qty,
                inward_qty=row.inward_qty,
                outward_qty=ZERO,
                balance_qty=row.inward_qty,
                from_stage=ProductionInventoryTransaction.Stage.GRANULATION_STORE,
                to_stage=ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
                reference_no=str(gl_batch.batch_no or "").strip() or None,
                scan_code=output_capture.scancode_id if output_capture else None,
                status=ProductionInventoryTransaction.Status.IN_PROGRESS,
                created_by=created_by,
            )
        )
    return moved_rows


def record_pr_final_capture(pr_batch: ProductionBatch, output_capture: ProductionOutputCapture, *, created_by=None) -> ProductionInventoryTransaction:
    production_code, production_name = _resolve_production_item_fields(pr_batch.production_order)
    quantity = Decimal(str(output_capture.weight_kg or ZERO))
    return upsert_inventory_transaction(
        movement_key=f"pr-final:line-work-center:{output_capture.id}",
        stage=ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
        batch_code=str(pr_batch.batch_no or "").strip(),
        production_order=pr_batch.production_order,
        source_batch=pr_batch,
        output_capture=output_capture,
        item=None,
        item_code=production_code,
        item_name=production_name,
        quantity=quantity,
        inward_qty=quantity,
        outward_qty=ZERO,
        balance_qty=quantity,
        from_stage=ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
        to_stage=ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
        reference_no=str(pr_batch.batch_no or "").strip() or None,
        scan_code=output_capture.scancode_id if output_capture else None,
        status=ProductionInventoryTransaction.Status.IN_PROGRESS,
        created_by=created_by,
    )


def move_pr_batch_to_line_work_center(pr_batch: ProductionBatch, output_capture: ProductionOutputCapture | None = None, *, created_by=None) -> list[ProductionInventoryTransaction]:
    moved_rows: list[ProductionInventoryTransaction] = []
    connection_rows = list(
        ProductionInventoryTransaction.objects.filter(
            stage=ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
            production_order=pr_batch.production_order,
            balance_qty__gt=ZERO,
        ).select_related("item", "production_order", "source_batch")
    )

    remaining_to_consume = Decimal(str(output_capture.weight_kg if output_capture is not None else ZERO))
    for row in connection_rows:
        if remaining_to_consume <= ZERO:
            break
        consume_qty = min(remaining_to_consume, Decimal(str(row.balance_qty or ZERO)))
        if consume_qty <= ZERO:
            continue

        row.outward_qty = Decimal(str(row.outward_qty or ZERO)) + consume_qty
        row.balance_qty = Decimal(str(row.balance_qty or ZERO)) - consume_qty
        row.to_stage = ProductionInventoryTransaction.Stage.LINE_WORK_CENTER
        row.status = (
            ProductionInventoryTransaction.Status.COMPLETED
            if row.balance_qty <= ZERO
            else ProductionInventoryTransaction.Status.IN_PROGRESS
        )
        row.save(update_fields=["outward_qty", "balance_qty", "to_stage", "status", "updated_at"])

        moved_rows.append(
            upsert_inventory_transaction(
                movement_key=f"pr-out:line-work-center:{pr_batch.id}:{row.id}",
                stage=ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
                batch_code=str(pr_batch.batch_no or "").strip(),
                production_order=pr_batch.production_order,
                source_batch=pr_batch,
                output_capture=output_capture,
                item=row.item,
                item_code=row.item_code,
                item_name=row.item_name,
                quantity=consume_qty,
                inward_qty=consume_qty,
                outward_qty=ZERO,
                balance_qty=consume_qty,
                from_stage=ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
                to_stage=ProductionInventoryTransaction.Stage.LINE_WORK_CENTER,
                reference_no=str(pr_batch.batch_no or "").strip() or None,
                scan_code=output_capture.scancode_id if output_capture else None,
                status=ProductionInventoryTransaction.Status.IN_PROGRESS,
                created_by=created_by,
            )
        )
        remaining_to_consume -= consume_qty

    return moved_rows
