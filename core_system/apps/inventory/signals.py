"""
Signal handlers for the production inventory app.

Connects to BlendingOutward to mirror blending issue movements
into ProductionInventoryTransaction records.

Flow:
    BlendingOutward created (reference_number = production_id)
        → ProductionInventoryTransaction(stage=BLENDING_WORK_CENTER, inward)

    BlendingOutward deleted
        → matching ProductionInventoryTransaction deleted
"""
from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

ZERO = Decimal("0.000")


def _resolve_work_center_name(production_order) -> str | None:
    """
    Extract the work center display name from the production order's extra_form_data.
    extra_form_data['work_center'] stores the WorkCentreCreationMaster pk as a string.
    """
    try:
        extra = production_order.extra_form_data or {}
        raw_id = extra.get("work_center", "")
        if not raw_id:
            return None
        from apps.production.models import WorkCentreCreationMaster
        wc = WorkCentreCreationMaster.objects.filter(pk=int(raw_id)).only("name", "code").first()
        if wc:
            return f"{wc.code} — {wc.name}" if wc.code else wc.name
        return str(raw_id)
    except Exception:
        return None


def on_blending_outward_saved(sender, instance, created, **kwargs):
    """
    When a BlendingOutward record is created and its reference_number matches
    a ProductionOrder.production_id, create a ProductionInventoryTransaction
    for the BLENDING_WORK_CENTER stage (inward movement).

    Skips update events (created=False) — quantity corrections should be
    handled as separate outward/adjustment entries.
    """
    if not created:
        return

    if not instance.reference_number:
        return

    try:
        from apps.production.models import ProductionOrder
        from .models import ProductionInventoryTransaction

        production_order = (
            ProductionOrder.objects
            .filter(production_id=instance.reference_number)
            .only("id", "production_id", "extra_form_data")
            .first()
        )

        if not production_order:
            # reference_number is not a production order — normal blending outward, skip
            return

        work_center_name = _resolve_work_center_name(production_order)

        ProductionInventoryTransaction.objects.update_or_create(
            movement_key=f"blending-outward:{instance.pk}",
            defaults={
                "stage": ProductionInventoryTransaction.Stage.BLENDING_WORK_CENTER,
                "batch_code": production_order.production_id,
                "production_order": production_order,
                "production_id": str(production_order.production_id or ""),
                "production_type": str(production_order.production_type or ""),
                "item": instance.item,
                "item_code": instance.item.item_code,
                "item_name": instance.item.item_name,
                "inward_qty": instance.quantity,
                "outward_qty": ZERO,
                "balance_qty": instance.quantity,
                "uom": instance.unit,
                "from_stage": "BLENDING_INVENTORY",
                "to_stage": ProductionInventoryTransaction.Stage.BLENDING_WORK_CENTER,
                "reference_no": production_order.production_id,
                "work_center": work_center_name,
                "status": ProductionInventoryTransaction.Status.IN_PROGRESS,
            },
        )

        logger.info(
            "inventory.signals: created BLENDING_WORK_CENTER inward | "
            "production=%s  item=%s  qty=%s",
            production_order.production_id,
            instance.item.item_code,
            instance.quantity,
        )

    except Exception:
        logger.exception(
            "inventory.signals: failed to create BLENDING_WORK_CENTER transaction "
            "for BlendingOutward pk=%s  reference=%s",
            instance.pk,
            instance.reference_number,
        )


def on_blending_outward_deleted(sender, instance, **kwargs):
    """
    When a BlendingOutward linked to a production order is deleted, remove
    the corresponding BLENDING_WORK_CENTER inward transaction.

    Matches on batch_code + item + inward_qty + from_stage to avoid
    touching unrelated records.
    """
    if not instance.reference_number:
        return

    try:
        from .models import ProductionInventoryTransaction

        deleted_count, _ = (
            ProductionInventoryTransaction.objects
            .filter(
                movement_key=f"blending-outward:{instance.pk}",
            )
            .delete()
        )

        if deleted_count:
            logger.info(
                "inventory.signals: deleted %d BLENDING_WORK_CENTER transaction(s) | "
                "BlendingOutward pk=%s  reference=%s",
                deleted_count,
                instance.pk,
                instance.reference_number,
            )

    except Exception:
        logger.exception(
            "inventory.signals: failed to delete BLENDING_WORK_CENTER transaction "
            "for BlendingOutward pk=%s  reference=%s",
            instance.pk,
            instance.reference_number,
        )
