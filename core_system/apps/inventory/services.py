from __future__ import annotations

from decimal import Decimal
import re
from django.db import models
from django.db.models import Q
from rest_framework.exceptions import ValidationError

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


def _resolve_weight_entry_item_fields(entry: BatchWeightEntry):
    item = entry.item or getattr(entry.bom_component, "item", None)
    if item is not None:
        return (
            item,
            str(getattr(item, "item_code", "") or "").strip(),
            str(getattr(item, "item_name", "") or "").strip(),
            str(getattr(item, "unit", "") or "").strip(),
        )

    bom_component = getattr(entry, "bom_component", None)
    if bom_component is None:
        return None, "", "", ""

    return (
        None,
        str(getattr(bom_component, "component_code", "") or "").strip(),
        str(getattr(bom_component, "component_name", "") or "").strip(),
        str(getattr(bom_component, "unit", "") or "").strip(),
    )


def _extract_workflow_suffix(value: str | None) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    match = re.search(r"(-\d+)$", text)
    if match:
        return match.group(1)
    return text


def _build_lineage_filters(lineage_suffix: str) -> Q:
    if not lineage_suffix:
        return Q()

    return (
        Q(batch_code__iendswith=lineage_suffix)
        | Q(reference_no__iendswith=lineage_suffix)
        | Q(source_batch__batch_no__iendswith=lineage_suffix)
        | Q(source_batch__workflow_batch_no__iendswith=lineage_suffix)
    )


def _normalize_context_token(value) -> str:
    return str(value or "").strip().casefold()


def _extract_inventory_context(order: ProductionOrder | None) -> dict[str, str]:
    extra = getattr(order, "extra_form_data", {}) or {}
    finished_goods = extra.get("finished_goods") if isinstance(extra.get("finished_goods"), dict) else {}
    return {
        "finished_good_id": _normalize_context_token(finished_goods.get("id")),
        "finished_good_code": _normalize_context_token(finished_goods.get("item_code")),
        "finished_good_name": _normalize_context_token(finished_goods.get("item_name")),
        "bom_variant_id": _normalize_context_token(extra.get("selected_bom_variant_id")),
        "work_center": _normalize_context_token(extra.get("work_center")),
        "production_facility": _normalize_context_token(extra.get("production_facility")),
    }


def _inventory_context_match_score(source_order: ProductionOrder | None, target_order: ProductionOrder | None) -> int:
    if source_order is None or target_order is None:
        return -1

    source_context = _extract_inventory_context(source_order)
    target_context = _extract_inventory_context(target_order)

    # Hard conflicts on finished-good identity or work center reject the row outright.
    for key in ("finished_good_id", "finished_good_code", "work_center"):
        source_value = source_context[key]
        target_value = target_context[key]
        if source_value and target_value and source_value != target_value:
            return -1

    score = 0

    if source_context["finished_good_id"] and source_context["finished_good_id"] == target_context["finished_good_id"]:
        score += 5
    if source_context["finished_good_code"] and source_context["finished_good_code"] == target_context["finished_good_code"]:
        score += 4
    if source_context["finished_good_name"] and source_context["finished_good_name"] == target_context["finished_good_name"]:
        score += 2
    if source_context["work_center"] and source_context["work_center"] == target_context["work_center"]:
        score += 2
    if source_context["bom_variant_id"] and source_context["bom_variant_id"] == target_context["bom_variant_id"]:
        score += 2
    if source_context["production_facility"] and source_context["production_facility"] == target_context["production_facility"]:
        score += 1

    return score


def _find_stage_stock_rows(
    *,
    stage: str,
    production_order: ProductionOrder | None,
    source_batch: ProductionBatch | None,
    lineage_batch_code: str | None = None,
    for_update: bool = False,
) -> list[ProductionInventoryTransaction]:
    queryset = ProductionInventoryTransaction.objects
    if for_update:
        queryset = queryset.select_for_update()

    queryset = queryset.filter(stage=stage, balance_qty__gt=ZERO).order_by("created_at", "id")

    if source_batch is not None:
        direct_rows = list(queryset.filter(source_batch=source_batch))
        if direct_rows:
            return direct_rows

    lineage_suffix = _extract_workflow_suffix(lineage_batch_code or getattr(source_batch, "batch_no", None))
    lineage_filters = _build_lineage_filters(lineage_suffix)

    if production_order is not None and lineage_filters:
        scoped_rows = list(queryset.filter(production_order=production_order).filter(lineage_filters))
        if scoped_rows:
            return scoped_rows

    if production_order is not None:
        scoped_rows = list(queryset.filter(production_order=production_order))
        if scoped_rows and not lineage_filters:
            return scoped_rows

    if production_order is not None:
        contextual_rows = []
        for row in queryset.select_related("production_order", "source_batch"):
            score = _inventory_context_match_score(getattr(row, "production_order", None), production_order)
            if score >= 6:
                contextual_rows.append((score, row))
        if contextual_rows:
            contextual_rows.sort(key=lambda entry: (-entry[0], entry[1].created_at, entry[1].id))
            return [row for _score, row in contextual_rows]

    if lineage_filters:
        global_rows = list(queryset.filter(lineage_filters))
        if global_rows:
            return global_rows

    return []


def _resolve_lineage_batch_code(
    source_rows: list[ProductionInventoryTransaction],
    *,
    fallback_batch_code: str,
) -> str:
    source_row = next(iter(source_rows), None)
    lineage_batch_code = ""
    if source_row is not None:
        lineage_batch_code = (
            str(source_row.batch_code or "").strip()
            or str(source_row.reference_no or "").strip()
            or str(getattr(getattr(source_row, "source_batch", None), "workflow_batch_no", "") or "").strip()
            or str(getattr(getattr(source_row, "source_batch", None), "batch_no", "") or "").strip()
        )
    if not lineage_batch_code:
        lineage_batch_code = str(fallback_batch_code or "").strip()
    return lineage_batch_code


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
        return []

    source_rows = _find_stage_stock_rows(
        stage=stage,
        production_order=production_order,
        source_batch=source_batch,
        lineage_batch_code=lineage_batch_code,
        for_update=True,
    )

    if not source_rows:
        raise ValidationError(f"No available stock found in {stage} for the selected PRD ID and batch.")

    available_qty = sum((Decimal(str(row.balance_qty or ZERO)) for row in source_rows), ZERO)
    if available_qty < quantity:
        raise ValidationError(
            f"Cannot move {quantity:.3f} from {stage}. Available stock is {available_qty:.3f}."
        )

    remaining_to_consume = quantity
    for row in source_rows:
        if remaining_to_consume <= ZERO:
            break

        current_balance = Decimal(str(row.balance_qty or ZERO))
        if current_balance <= ZERO:
            continue

        consume_qty = min(current_balance, remaining_to_consume)
        row.outward_qty = Decimal(str(row.outward_qty or ZERO)) + consume_qty
        row.balance_qty = current_balance - consume_qty
        row.to_stage = next_stage
        row.status = (
            ProductionInventoryTransaction.Status.COMPLETED
            if row.balance_qty <= ZERO
            else ProductionInventoryTransaction.Status.IN_PROGRESS
        )
        row.save(update_fields=["outward_qty", "balance_qty", "to_stage", "status", "updated_at"])
        remaining_to_consume -= consume_qty
    return source_rows


def get_available_stage_quantity(production_order: ProductionOrder, stage: str) -> Decimal:
    total = ProductionInventoryTransaction.objects.filter(
        production_order=production_order,
        stage=stage,
        balance_qty__gt=ZERO,
    ).aggregate(total=models.Sum("balance_qty"))
    return Decimal(str(total.get("total") or ZERO))


def get_available_stage_quantity_for_context(
    *,
    production_order: ProductionOrder,
    stage: str,
    source_batch: ProductionBatch | None = None,
    lineage_batch_code: str | None = None,
) -> Decimal:
    rows = _find_stage_stock_rows(
        stage=stage,
        production_order=production_order,
        source_batch=source_batch,
        lineage_batch_code=lineage_batch_code,
        for_update=False,
    )
    return sum((Decimal(str(row.balance_qty or ZERO)) for row in rows), ZERO)


def upsert_inventory_transaction(
    *,
    movement_key: str,
    stage: str,
    batch_code: str,
    production_order: ProductionOrder,
    production_id: str | None = None,
    production_type: str | None = None,
    source_batch: ProductionBatch | None = None,
    output_capture: ProductionOutputCapture | None = None,
    item=None,
    item_code: str = "",
    item_name: str = "",
    uom: str | None = None,
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
        "production_id": str(production_id if production_id is not None else production_order.production_id or "").strip(),
        "production_type": str(production_type if production_type is not None else production_order.production_type or "").strip(),
        "source_batch": source_batch,
        "output_capture": output_capture,
        "item": item,
        "item_code": item_code or getattr(item, "item_code", "") or "",
        "item_name": item_name or getattr(item, "item_name", "") or "",
        "inward_qty": resolved_inward_qty,
        "outward_qty": resolved_outward_qty,
        "balance_qty": resolved_balance_qty,
        "uom": str(uom if uom is not None else getattr(item, "unit", "") or "").strip(),
        "from_stage": from_stage,
        "to_stage": to_stage,
        "reference_no": reference_no or str(batch_code or "").strip() or str(production_order.production_id or "").strip() or None,
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

    item, item_code, item_name, uom = _resolve_weight_entry_item_fields(entry)
    if not item_code and not item_name:
        return None

    quantity = Decimal(str(entry.entered_weight_grams or ZERO))
    return upsert_inventory_transaction(
        movement_key=f"ad-save:{entry.id}",
        stage=ProductionInventoryTransaction.Stage.ADDITIVE_WORK_CENTER,
        batch_code=str(entry.batch.batch_no or "").strip(),
        production_order=entry.batch.production_order,
        source_batch=entry.batch,
        item=item,
        item_code=item_code,
        item_name=item_name,
        uom=uom,
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


def finalize_ad_batch_to_additive_store(
    ad_batch: ProductionBatch,
    *,
    created_by=None,
) -> list[ProductionInventoryTransaction]:
    finalized_rows: list[ProductionInventoryTransaction] = []
    for entry in _iter_batch_weight_entries(ad_batch):
        if entry.entered_weight_grams is None:
            continue

        item, item_code, item_name, uom = _resolve_weight_entry_item_fields(entry)
        if not item_code and not item_name:
            continue

        quantity = Decimal(str(entry.entered_weight_grams or ZERO))
        finalized_rows.append(
            upsert_inventory_transaction(
                movement_key=f"ad-save:{entry.id}",
                stage=ProductionInventoryTransaction.Stage.ADDITIVE_WORK_CENTER,
                batch_code=str(ad_batch.batch_no or "").strip(),
                production_order=ad_batch.production_order,
                source_batch=ad_batch,
                item=item,
                item_code=item_code,
                item_name=item_name,
                uom=uom,
                quantity=quantity,
                inward_qty=quantity,
                outward_qty=ZERO,
                balance_qty=quantity,
                from_stage="AD",
                to_stage=ProductionInventoryTransaction.Stage.ADDITIVE_WORK_CENTER,
                reference_no=str(ad_batch.production_order.production_id or "").strip() or None,
                status=ProductionInventoryTransaction.Status.COMPLETED,
                created_by=created_by,
            )
        )
    return finalized_rows


def move_ad_batch_to_blend_wip(ad_batch: ProductionBatch, *, created_by=None) -> list[ProductionInventoryTransaction]:
    moved_rows: list[ProductionInventoryTransaction] = []
    for entry in _iter_batch_weight_entries(ad_batch):
        if entry.entered_weight_grams is None:
            continue
        item, item_code, item_name, uom = _resolve_weight_entry_item_fields(entry)
        if not item_code and not item_name:
            continue

        quantity = Decimal(str(entry.entered_weight_grams or ZERO))
        upsert_inventory_transaction(
            movement_key=f"ad-save:{entry.id}",
            stage=ProductionInventoryTransaction.Stage.ADDITIVE_WORK_CENTER,
            batch_code=str(ad_batch.batch_no or "").strip(),
            production_order=ad_batch.production_order,
            source_batch=ad_batch,
            item=item,
            item_code=item_code,
            item_name=item_name,
            uom=uom,
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
                item_code=item_code,
                item_name=item_name,
                uom=uom,
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


def record_bl_final_capture(
    bl_batch: ProductionBatch,
    output_capture: ProductionOutputCapture,
    *,
    created_by=None,
    source_order: ProductionOrder | None = None,
) -> ProductionInventoryTransaction:
    production_code, production_name = _resolve_production_item_fields(bl_batch.production_order)
    quantity = Decimal(str(output_capture.weight_kg or ZERO))

    source_batch = getattr(bl_batch, "parent_batch", None)
    source_rows = _consume_stage_quantity(
        stage=ProductionInventoryTransaction.Stage.BLEND_WIP,
        next_stage=ProductionInventoryTransaction.Stage.BLEND_STORE,
        quantity=quantity,
        production_order=source_order or bl_batch.production_order,
        source_batch=source_batch,
        lineage_batch_code=str(bl_batch.batch_no or "").strip() or None,
    )
    lineage_batch_code = _resolve_lineage_batch_code(
        source_rows,
        fallback_batch_code=str(bl_batch.batch_no or "").strip(),
    )

    return upsert_inventory_transaction(
        movement_key=f"bl-final:blend-store:{output_capture.id}",
        stage=ProductionInventoryTransaction.Stage.BLEND_STORE,
        batch_code=lineage_batch_code,
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
        from_stage=ProductionInventoryTransaction.Stage.BLEND_WIP,
        to_stage=ProductionInventoryTransaction.Stage.BLEND_STORE,
        reference_no=lineage_batch_code or None,
        scan_code=str(output_capture.scancode_id or "").strip() or None,
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

    if not blend_store_rows:
        raise ValidationError("No available Blend Store stock found to move into Granulation Work Center.")

    for row in blend_store_rows:
        available_qty = Decimal(str(row.balance_qty or ZERO))
        row.outward_qty = Decimal(str(row.outward_qty or ZERO)) + available_qty
        row.balance_qty = ZERO
        row.to_stage = ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER
        row.status = ProductionInventoryTransaction.Status.COMPLETED
        row.save(update_fields=["outward_qty", "balance_qty", "to_stage", "status", "updated_at"])

        moved_rows.append(
            upsert_inventory_transaction(
                movement_key=f"bl-out:gran-work-center:{row.id}",
                stage=ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER,
                batch_code=str(row.batch_code or row.reference_no or "").strip(),
                production_order=bl_batch.production_order,
                source_batch=bl_batch,
                output_capture=output_capture,
                item=row.item,
                item_code=row.item_code,
                item_name=row.item_name,
                quantity=available_qty,
                inward_qty=available_qty,
                outward_qty=ZERO,
                balance_qty=available_qty,
                from_stage=ProductionInventoryTransaction.Stage.BLEND_STORE,
                to_stage=ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER,
                reference_no=str(row.batch_code or row.reference_no or "").strip() or None,
                scan_code=output_capture.scancode_id if output_capture else None,
                status=ProductionInventoryTransaction.Status.IN_PROGRESS,
                created_by=created_by,
            )
        )
    return moved_rows


def record_gl_final_capture(
    gl_batch: ProductionBatch,
    output_capture: ProductionOutputCapture,
    *,
    created_by=None,
    source_order: ProductionOrder | None = None,
) -> ProductionInventoryTransaction:
    production_code, production_name = _resolve_production_item_fields(gl_batch.production_order)
    quantity = Decimal(str(output_capture.weight_kg or ZERO))

    source_rows = _consume_stage_quantity(
        stage=ProductionInventoryTransaction.Stage.GRANULATION_WORK_CENTER,
        next_stage=ProductionInventoryTransaction.Stage.GRANULATION_STORE,
        quantity=quantity,
        production_order=source_order or gl_batch.production_order,
        source_batch=getattr(gl_batch, "parent_batch", None),
        lineage_batch_code=str(gl_batch.batch_no or "").strip() or None,
    )
    lineage_batch_code = _resolve_lineage_batch_code(
        source_rows,
        fallback_batch_code=str(gl_batch.batch_no or "").strip(),
    )

    return upsert_inventory_transaction(
        movement_key=f"gl-final:granulation-store:{output_capture.id}",
        stage=ProductionInventoryTransaction.Stage.GRANULATION_STORE,
        batch_code=lineage_batch_code,
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
        reference_no=lineage_batch_code or None,
        scan_code=str(output_capture.scancode_id or "").strip() or None,
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

    if not gran_store_rows:
        raise ValidationError("No available Granulation Store stock found to move into Connection to Line.")

    for row in gran_store_rows:
        available_qty = Decimal(str(row.balance_qty or ZERO))
        row.outward_qty = Decimal(str(row.outward_qty or ZERO)) + available_qty
        row.balance_qty = ZERO
        row.to_stage = ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE
        row.status = ProductionInventoryTransaction.Status.COMPLETED
        row.save(update_fields=["outward_qty", "balance_qty", "to_stage", "status", "updated_at"])

        moved_rows.append(
            upsert_inventory_transaction(
                movement_key=f"gl-out:connection-line:{row.id}",
                stage=ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
                batch_code=str(row.batch_code or row.reference_no or "").strip(),
                production_order=gl_batch.production_order,
                source_batch=gl_batch,
                output_capture=output_capture,
                item=row.item,
                item_code=row.item_code,
                item_name=row.item_name,
                quantity=available_qty,
                inward_qty=available_qty,
                outward_qty=ZERO,
                balance_qty=available_qty,
                from_stage=ProductionInventoryTransaction.Stage.GRANULATION_STORE,
                to_stage=ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
                reference_no=str(row.batch_code or row.reference_no or "").strip() or None,
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


def move_pr_batch_to_line_work_center(
    pr_batch: ProductionBatch,
    output_capture: ProductionOutputCapture | None = None,
    *,
    created_by=None,
    source_order: ProductionOrder | None = None,
) -> list[ProductionInventoryTransaction]:
    moved_rows: list[ProductionInventoryTransaction] = []
    connection_rows = list(
        ProductionInventoryTransaction.objects.filter(
            stage=ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
            production_order=source_order or pr_batch.production_order,
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
                batch_code=str(row.batch_code or row.reference_no or pr_batch.batch_no or "").strip(),
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
                reference_no=str(row.batch_code or row.reference_no or pr_batch.batch_no or "").strip() or None,
                scan_code=output_capture.scancode_id if output_capture else None,
                status=ProductionInventoryTransaction.Status.IN_PROGRESS,
                created_by=created_by,
            )
        )
        remaining_to_consume -= consume_qty

    return moved_rows
