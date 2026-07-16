"""Business logic for the Extrusion Production / Packing / Weight Verification /
Sticker Generation / Scrap KPI module. Views stay thin and delegate here,
mirroring the existing `apps.production.services` convention.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, DecimalField, F, Max, Q, Sum
from django.db.models.functions import Abs, Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .extrusion_models import (
    ExtrusionAuditLog,
    ExtrusionInspection,
    ExtrusionWorkOrder,
    Packet,
    PacketSticker,
    PacketWeightAttempt,
    ScrapTransaction,
    StickerScanLog,
)

ZERO = Decimal("0.000")


def _log(*, entity_type: str, entity_id, action: str, actor=None, reason: str = "", remarks: str = "",
          old_value: dict | None = None, new_value: dict | None = None, source: str = "web") -> None:
    ExtrusionAuditLog.objects.create(
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        reason=reason,
        remarks=remarks,
        old_value=old_value or {},
        new_value=new_value or {},
        source=source,
    )


# ---------------------------------------------------------------------------
# Work order
# ---------------------------------------------------------------------------

def release_work_order(work_order: ExtrusionWorkOrder, *, user) -> ExtrusionWorkOrder:
    if work_order.status != ExtrusionWorkOrder.Status.DRAFT:
        raise ValidationError("Only draft work orders can be released.")
    if not work_order.consumables.exists():
        raise ValidationError("At least one consumable is required before release.")
    if not work_order.packing_material_id:
        raise ValidationError("Packing material is required before release.")
    if work_order.expected_tare_weight is None or work_order.expected_tare_weight < 0:
        raise ValidationError("A valid tare weight is required before release.")
    if not work_order.expected_section_weight_per_meter or work_order.expected_section_weight_per_meter <= 0:
        raise ValidationError("Profile section weight is required before release.")

    with transaction.atomic():
        work_order.status = ExtrusionWorkOrder.Status.RELEASED
        work_order.released_by = user if getattr(user, "is_authenticated", False) else None
        work_order.released_at = timezone.now()
        work_order.save(update_fields=["status", "released_by", "released_at", "updated_at"])
        _log(entity_type="work_order", entity_id=work_order.pk, action="RELEASED", actor=user)
    return work_order


def assert_work_order_editable(work_order: ExtrusionWorkOrder, *, critical_fields: set[str] | None = None) -> None:
    if work_order.is_locked_for_critical_edits and critical_fields:
        raise ValidationError(
            "Critical fields cannot be edited once the work order has production, packet, weighing or "
            "sticker transactions."
        )


# ---------------------------------------------------------------------------
# Quality inspection
# ---------------------------------------------------------------------------

def create_or_update_inspection(instance: ExtrusionInspection, *, user) -> ExtrusionInspection:
    instance.compute_overall_result()
    if not instance.inspected_by_id:
        instance.inspected_by = user if getattr(user, "is_authenticated", False) else None
    instance.full_clean()
    instance.save()
    _log(
        entity_type="inspection",
        entity_id=instance.pk,
        action="RECORDED",
        actor=user,
        new_value={"overall_result": instance.overall_result, "decision": instance.rejection_decision},
    )
    return instance


# ---------------------------------------------------------------------------
# Packet creation
# ---------------------------------------------------------------------------

def create_packet(
    *,
    work_order: ExtrusionWorkOrder,
    inspection: ExtrusionInspection,
    pieces: int,
    length_per_piece: Decimal,
    packing_material,
    tare_weight: Decimal | None,
    user,
) -> Packet:
    if inspection.work_order_id != work_order.pk:
        raise ValidationError("Inspection does not belong to this work order.")
    if not inspection.is_accepted:
        raise ValidationError("Only accepted inspections are eligible for packing.")
    if pieces <= 0:
        raise ValidationError("Pieces must be greater than zero.")
    if length_per_piece is None or length_per_piece <= 0:
        raise ValidationError("Length per piece must be greater than zero.")

    packet = Packet(
        work_order=work_order,
        inspection=inspection,
        pieces=pieces,
        length_per_piece=length_per_piece,
        packing_material=packing_material,
        tare_weight=tare_weight if tare_weight is not None else work_order.expected_tare_weight,
        section_weight_per_meter=work_order.expected_section_weight_per_meter,
        tolerance_type=work_order.tolerance_type,
        tolerance_value=work_order.tolerance_value,
        status=Packet.Status.AWAITING_WEIGHT,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    packet.compute_expected_values()

    with transaction.atomic():
        packet.full_clean()
        packet.save()
        if work_order.status in (ExtrusionWorkOrder.Status.RELEASED, ExtrusionWorkOrder.Status.IN_PRODUCTION):
            work_order.status = ExtrusionWorkOrder.Status.PACKING_IN_PROGRESS
            work_order.save(update_fields=["status", "updated_at"])
        _log(entity_type="packet", entity_id=packet.pk, action="CREATED", actor=user)
    return packet


# ---------------------------------------------------------------------------
# Weighing
# ---------------------------------------------------------------------------

def record_weight_attempt(
    *,
    packet: Packet,
    actual_gross_weight: Decimal,
    user,
    source: str = PacketWeightAttempt.Source.SCALE,
    device_id: str = "",
    workstation_id: str = "",
    bridge_client_id: str = "",
    is_override: bool = False,
    override_reason: str = "",
) -> PacketWeightAttempt:
    if packet.status in (Packet.Status.SCRAPPED, Packet.Status.CANCELLED, Packet.Status.QC_APPROVED,
                          Packet.Status.MOVED_TO_WAREHOUSE):
        raise ValidationError(f"Packet in status {packet.status} cannot be reweighed.")
    if actual_gross_weight is None or actual_gross_weight <= 0:
        raise ValidationError("A valid actual gross weight is required.")
    if is_override and not str(override_reason or "").strip():
        raise ValidationError("A reason is required for manual weight override.")

    result = packet.evaluate_weight(actual_gross_weight)
    deviation = (Decimal(actual_gross_weight) - packet.expected_gross_weight).quantize(Decimal("0.001"))
    deviation_pct = (
        (deviation / packet.expected_gross_weight * Decimal("100")).quantize(Decimal("0.001"))
        if packet.expected_gross_weight
        else ZERO
    )
    next_attempt_no = packet.weight_attempts.count() + 1

    with transaction.atomic():
        attempt = PacketWeightAttempt.objects.create(
            packet=packet,
            attempt_no=next_attempt_no,
            actual_gross_weight=actual_gross_weight,
            result=result,
            weight_deviation=deviation,
            deviation_percentage=deviation_pct,
            source=source,
            device_id=device_id,
            workstation_id=workstation_id,
            bridge_client_id=bridge_client_id,
            is_override=is_override,
            override_reason=override_reason,
            override_by=(user if is_override and getattr(user, "is_authenticated", False) else None),
            weighed_by=user if getattr(user, "is_authenticated", False) else None,
        )
        packet.actual_gross_weight = actual_gross_weight
        packet.weight_deviation = deviation
        packet.deviation_percentage = deviation_pct
        packet.status = (
            Packet.Status.WEIGHT_ACCEPTED if result == PacketWeightAttempt.Result.ACCEPTED
            else Packet.Status.WEIGHT_REJECTED
        )
        packet.save(update_fields=[
            "actual_gross_weight", "weight_deviation", "deviation_percentage", "status", "updated_at",
        ])
        _log(
            entity_type="packet",
            entity_id=packet.pk,
            action="WEIGHT_OVERRIDE" if is_override else "WEIGHED",
            actor=user,
            reason=override_reason,
            new_value={"attempt_no": next_attempt_no, "result": result, "weight": str(actual_gross_weight)},
        )
    return attempt


# ---------------------------------------------------------------------------
# Sticker generation / scanning
# ---------------------------------------------------------------------------

def _build_sticker_payload(packet: Packet) -> dict:
    work_order = packet.work_order
    profile = work_order.profile
    return {
        "packet_number": packet.packet_no,
        "work_order_number": work_order.work_order_no,
        "date": str(work_order.production_date),
        "shift": work_order.shift,
        "line_number": work_order.extrusion_line.code,
        "line_name": work_order.extrusion_line.name,
        "profile_id": profile.code,
        "profile_description": profile.name,
        "alloy": getattr(profile, "description", ""),
        "pieces": packet.pieces,
        "length": str(packet.length_per_piece),
        "total_meters": str(packet.total_meters),
        "section_weight": str(packet.section_weight_per_meter),
        "net_weight": str(packet.expected_net_weight),
        "tare_weight": str(packet.tare_weight),
        "gross_weight": str(packet.expected_gross_weight),
        "qc_status": packet.inspection.overall_result,
    }


def generate_sticker(packet: Packet, *, user) -> PacketSticker:
    if packet.status != Packet.Status.WEIGHT_ACCEPTED:
        raise ValidationError("Sticker can only be generated for weight-accepted packets.")
    if PacketSticker.objects.filter(packet=packet).exists():
        raise ValidationError("A sticker already exists for this packet.")

    with transaction.atomic():
        sticker = PacketSticker.objects.create(
            packet=packet,
            qr_payload=_build_sticker_payload(packet),
            generated_by=user if getattr(user, "is_authenticated", False) else None,
        )
        packet.status = Packet.Status.STICKER_GENERATED
        packet.save(update_fields=["status", "updated_at"])
        _log(entity_type="sticker", entity_id=sticker.pk, action="GENERATED", actor=user)
    return sticker


def reprint_sticker(sticker: PacketSticker, *, user, reason: str) -> PacketSticker:
    if not str(reason or "").strip():
        raise ValidationError("A reason is required to reprint a sticker.")
    if sticker.status != PacketSticker.Status.ACTIVE:
        raise ValidationError(f"Cannot reprint a sticker in status {sticker.status}.")

    with transaction.atomic():
        sticker.reprint_count = F("reprint_count") + 1
        sticker.last_reprint_reason = reason
        sticker.last_reprint_by = user if getattr(user, "is_authenticated", False) else None
        sticker.last_reprint_at = timezone.now()
        sticker.save(update_fields=[
            "reprint_count", "last_reprint_reason", "last_reprint_by", "last_reprint_at", "updated_at",
        ])
        sticker.refresh_from_db()
        _log(entity_type="sticker", entity_id=sticker.pk, action="REPRINT", actor=user, reason=reason)
    return sticker


def scan_sticker(sticker: PacketSticker, *, packet: Packet | None, user) -> PacketSticker:
    if packet is not None and sticker.packet_id != packet.pk:
        StickerScanLog.objects.create(
            sticker=sticker, packet=packet, result=StickerScanLog.Result.MISMATCH,
            scanned_by=user if getattr(user, "is_authenticated", False) else None,
        )
        raise ValidationError("This sticker does not belong to the scanned packet.")

    if sticker.status != PacketSticker.Status.ACTIVE:
        StickerScanLog.objects.create(
            sticker=sticker, packet=sticker.packet,
            result=StickerScanLog.Result.CANCELLED if sticker.status != PacketSticker.Status.ACTIVE else StickerScanLog.Result.OK,
            scanned_by=user if getattr(user, "is_authenticated", False) else None,
        )
        raise ValidationError(f"Sticker is {sticker.status.lower()} and cannot be scanned.")

    if sticker.scanned_at is not None:
        StickerScanLog.objects.create(
            sticker=sticker, packet=sticker.packet, result=StickerScanLog.Result.ALREADY_USED,
            scanned_by=user if getattr(user, "is_authenticated", False) else None,
        )
        raise ValidationError("This sticker has already been scanned.")

    with transaction.atomic():
        sticker.scanned_by = user if getattr(user, "is_authenticated", False) else None
        sticker.scanned_at = timezone.now()
        sticker.save(update_fields=["scanned_by", "scanned_at", "updated_at"])
        sticker.packet.status = Packet.Status.STICKER_SCANNED
        sticker.packet.save(update_fields=["status", "updated_at"])
        StickerScanLog.objects.create(
            sticker=sticker, packet=sticker.packet, result=StickerScanLog.Result.OK,
            scanned_by=user if getattr(user, "is_authenticated", False) else None,
        )
        _log(entity_type="sticker", entity_id=sticker.pk, action="SCANNED", actor=user)
    return sticker


# ---------------------------------------------------------------------------
# Shift-end QC approval
# ---------------------------------------------------------------------------

def eligible_packets_for_approval(*, date_from=None, date_to=None, shift=None, line=None, work_order=None,
                                    profile=None):
    queryset = Packet.objects.filter(status=Packet.Status.STICKER_SCANNED)
    if date_from:
        queryset = queryset.filter(work_order__production_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(work_order__production_date__lte=date_to)
    if shift:
        queryset = queryset.filter(work_order__shift=shift)
    if line:
        queryset = queryset.filter(work_order__extrusion_line_id=line)
    if work_order:
        queryset = queryset.filter(work_order_id=work_order)
    if profile:
        queryset = queryset.filter(work_order__profile_id=profile)
    return queryset


def approve_packets(packets, *, user, remarks: str = "") -> list[Packet]:
    approved: list[Packet] = []
    now = timezone.now()
    with transaction.atomic():
        for packet in packets:
            if packet.status != Packet.Status.STICKER_SCANNED:
                continue
            packet.status = Packet.Status.QC_APPROVED
            packet.qc_approved_by = user if getattr(user, "is_authenticated", False) else None
            packet.qc_approved_at = now
            packet.qc_approval_remarks = remarks
            packet.save(update_fields=[
                "status", "qc_approved_by", "qc_approved_at", "qc_approval_remarks", "updated_at",
            ])
            _log(entity_type="packet", entity_id=packet.pk, action="QC_APPROVED", actor=user, remarks=remarks)
            approved.append(packet)
    return approved


def reverse_qc_approval(packet: Packet, *, user, reason: str) -> Packet:
    if not str(reason or "").strip():
        raise ValidationError("A reason is required to reverse a QC approval.")
    if packet.status != Packet.Status.QC_APPROVED:
        raise ValidationError("Only QC-approved packets can be reversed.")

    with transaction.atomic():
        packet.status = Packet.Status.STICKER_SCANNED
        packet.qc_approved_by = None
        packet.qc_approved_at = None
        packet.save(update_fields=["status", "qc_approved_by", "qc_approved_at", "updated_at"])
        _log(entity_type="packet", entity_id=packet.pk, action="QC_APPROVAL_REVERSED", actor=user, reason=reason)
    return packet


# ---------------------------------------------------------------------------
# Warehouse transfer
# ---------------------------------------------------------------------------

def receive_at_warehouse(packet: Packet, *, user, warehouse_id=None) -> Packet:
    if packet.status != Packet.Status.QC_APPROVED:
        raise ValidationError("Only QC-approved packets can be received into the warehouse.")

    with transaction.atomic():
        packet.status = Packet.Status.MOVED_TO_WAREHOUSE
        packet.warehouse_id = warehouse_id
        packet.warehouse_received_by = user if getattr(user, "is_authenticated", False) else None
        packet.warehouse_received_at = timezone.now()
        packet.save(update_fields=[
            "status", "warehouse", "warehouse_received_by", "warehouse_received_at", "updated_at",
        ])
        _log(entity_type="packet", entity_id=packet.pk, action="WAREHOUSE_RECEIVED", actor=user)
    return packet


# ---------------------------------------------------------------------------
# Scrap management
# ---------------------------------------------------------------------------

def create_scrap_transaction(
    *,
    source_stage: str,
    work_order: ExtrusionWorkOrder,
    inspection: ExtrusionInspection | None,
    packet: Packet | None,
    scrap_category,
    scrap_reason,
    actual_scrap_weight: Decimal,
    remarks: str,
    production_date,
    shift: str,
    user,
) -> ScrapTransaction:
    if actual_scrap_weight is None or actual_scrap_weight <= 0:
        raise ValidationError("Actual scrap weight must be greater than zero.")

    duplicate_filter = Q(work_order=work_order, status__in=ScrapTransaction.ACTIVE_STATUSES)
    if packet is not None:
        duplicate_filter &= Q(packet=packet)
    elif inspection is not None:
        duplicate_filter &= Q(inspection=inspection, packet__isnull=True)
    if ScrapTransaction.objects.filter(duplicate_filter).exists():
        raise ValidationError("An active scrap transaction already exists for this record.")

    scrap = ScrapTransaction(
        source_stage=source_stage,
        work_order=work_order,
        profile=work_order.profile,
        inspection=inspection,
        packet=packet,
        production_date=production_date,
        shift=shift,
        scrap_category=scrap_category,
        scrap_reason=scrap_reason,
        actual_scrap_weight=actual_scrap_weight,
        remarks=remarks,
        status=ScrapTransaction.Status.CONFIRMED,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )

    with transaction.atomic():
        scrap.full_clean()
        scrap.save()

        if packet is not None:
            sticker = getattr(packet, "sticker", None)
            if sticker is not None and sticker.status == PacketSticker.Status.ACTIVE:
                sticker.status = PacketSticker.Status.SCRAPPED
                sticker.cancelled_by = user if getattr(user, "is_authenticated", False) else None
                sticker.cancelled_at = timezone.now()
                sticker.cancellation_reason = f"Packet scrapped: {scrap_reason.name}"
                sticker.save(update_fields=[
                    "status", "cancelled_by", "cancelled_at", "cancellation_reason", "updated_at",
                ])
            packet.status = Packet.Status.SCRAPPED
            packet.save(update_fields=["status", "updated_at"])

        _log(
            entity_type="scrap_transaction", entity_id=scrap.pk, action="CREATED", actor=user,
            new_value={"weight": str(actual_scrap_weight), "stage": source_stage},
        )
    return scrap


def approve_scrap_transaction(scrap: ScrapTransaction, *, user) -> ScrapTransaction:
    if scrap.status != ScrapTransaction.Status.CONFIRMED:
        raise ValidationError("Only confirmed scrap transactions can be approved.")
    with transaction.atomic():
        scrap.status = ScrapTransaction.Status.APPROVED
        scrap.approved_by = user if getattr(user, "is_authenticated", False) else None
        scrap.approved_at = timezone.now()
        scrap.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        _log(entity_type="scrap_transaction", entity_id=scrap.pk, action="APPROVED", actor=user)
    return scrap


def reverse_scrap_transaction(scrap: ScrapTransaction, *, user, reason: str) -> ScrapTransaction:
    if not str(reason or "").strip():
        raise ValidationError("A reason is required to reverse a scrap transaction.")
    if scrap.status == ScrapTransaction.Status.REVERSED:
        raise ValidationError("This scrap transaction is already reversed.")

    with transaction.atomic():
        scrap.status = ScrapTransaction.Status.REVERSED
        scrap.reversed_by = user if getattr(user, "is_authenticated", False) else None
        scrap.reversed_at = timezone.now()
        scrap.reversal_reason = reason
        scrap.save(update_fields=["status", "reversed_by", "reversed_at", "reversal_reason", "updated_at"])

        packet = scrap.packet
        if packet is not None and packet.status == Packet.Status.SCRAPPED:
            packet.status = Packet.Status.STICKER_SCANNED
            packet.save(update_fields=["status", "updated_at"])
            sticker = getattr(packet, "sticker", None)
            if sticker is not None and sticker.status == PacketSticker.Status.SCRAPPED:
                sticker.status = PacketSticker.Status.ACTIVE
                sticker.save(update_fields=["status", "updated_at"])

        _log(entity_type="scrap_transaction", entity_id=scrap.pk, action="REVERSED", actor=user, reason=reason)
    return scrap


# ---------------------------------------------------------------------------
# KPI dashboard
# ---------------------------------------------------------------------------

DECIMAL_FIELD = DecimalField(max_digits=18, decimal_places=3)


def _apply_common_filters(queryset, *, prefix: str, work_order_field: str, filters: dict):
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    work_order = filters.get("work_order")
    profile = filters.get("profile")
    shift = filters.get("shift")
    line = filters.get("line")

    if date_from:
        queryset = queryset.filter(**{f"{prefix}production_date__gte": date_from})
    if date_to:
        queryset = queryset.filter(**{f"{prefix}production_date__lte": date_to})
    if work_order:
        queryset = queryset.filter(**{work_order_field: work_order})
    if profile:
        queryset = queryset.filter(**{f"{prefix}profile_id": profile})
    if shift:
        queryset = queryset.filter(**{f"{prefix}shift": shift})
    if line:
        queryset = queryset.filter(**{f"{prefix}extrusion_line_id": line})
    return queryset


def compute_scrap_kpis(filters: dict) -> dict:
    packet_qs = Packet.objects.filter(status__in=[Packet.Status.QC_APPROVED, Packet.Status.MOVED_TO_WAREHOUSE])
    packet_qs = _apply_common_filters(
        packet_qs, prefix="work_order__", work_order_field="work_order_id", filters=filters
    )

    scrap_qs = ScrapTransaction.objects.filter(status__in=ScrapTransaction.ACTIVE_STATUSES)
    scrap_qs = _apply_common_filters(scrap_qs, prefix="", work_order_field="work_order_id", filters=filters)
    if filters.get("scrap_stage"):
        scrap_qs = scrap_qs.filter(source_stage=filters["scrap_stage"])
    if filters.get("scrap_category"):
        scrap_qs = scrap_qs.filter(scrap_category_id=filters["scrap_category"])
    if filters.get("scrap_reason"):
        scrap_qs = scrap_qs.filter(scrap_reason_id=filters["scrap_reason"])

    accepted_weight = packet_qs.aggregate(
        total=Coalesce(Sum("expected_net_weight", output_field=DECIMAL_FIELD), ZERO)
    )["total"]
    scrap_weight = scrap_qs.aggregate(
        total=Coalesce(Sum("actual_scrap_weight", output_field=DECIMAL_FIELD), ZERO)
    )["total"]
    total_weight = accepted_weight + scrap_weight
    scrap_percentage = (scrap_weight / total_weight * 100) if total_weight else ZERO
    recovery_percentage = (accepted_weight / total_weight * 100) if total_weight else ZERO

    weighed_packets = Packet.objects.filter(weight_attempts__isnull=False).distinct()
    weighed_packets = _apply_common_filters(
        weighed_packets, prefix="work_order__", work_order_field="work_order_id", filters=filters
    )
    total_weighed = weighed_packets.count()
    first_pass_count = weighed_packets.filter(
        weight_attempts__attempt_no=1, weight_attempts__result=PacketWeightAttempt.Result.ACCEPTED
    ).count()
    reweighed_count = weighed_packets.annotate(attempt_count=Count("weight_attempts")).filter(
        attempt_count__gt=1
    ).count()

    attempt_qs = PacketWeightAttempt.objects.filter(packet__in=weighed_packets)
    deviation_stats = attempt_qs.aggregate(
        avg_deviation=Coalesce(Avg("weight_deviation", output_field=DECIMAL_FIELD), ZERO),
        max_deviation=Coalesce(Max(Abs("weight_deviation"), output_field=DECIMAL_FIELD), ZERO),
        underweight_count=Count("id", filter=Q(result=PacketWeightAttempt.Result.UNDERWEIGHT)),
        overweight_count=Count("id", filter=Q(result=PacketWeightAttempt.Result.OVERWEIGHT)),
    )

    cost_per_kg = filters.get("cost_per_kg")
    scrap_cost = (scrap_weight * Decimal(str(cost_per_kg))) if cost_per_kg else None

    def _grouped(queryset, group_field: str, label_field: str):
        rows = (
            queryset.values(group_field)
            .annotate(label=F(label_field), weight=Sum("actual_scrap_weight", output_field=DECIMAL_FIELD))
            .order_by("-weight")
        )
        results = []
        for row in rows:
            weight = row["weight"] or ZERO
            results.append({
                "id": row[group_field],
                "label": row["label"],
                "weight": weight,
                "percentage": (weight / scrap_weight * 100) if scrap_weight else ZERO,
            })
        return results

    return {
        "accepted_production_weight": accepted_weight,
        "total_scrap_weight": scrap_weight,
        "total_production_weight": total_weight,
        "scrap_percentage": scrap_percentage.quantize(Decimal("0.01")) if total_weight else ZERO,
        "material_recovery_percentage": recovery_percentage.quantize(Decimal("0.01")) if total_weight else ZERO,
        "scrap_cost": scrap_cost,
        "first_pass_weight_acceptance_percentage": (
            (Decimal(first_pass_count) / Decimal(total_weighed) * 100).quantize(Decimal("0.01"))
            if total_weighed else ZERO
        ),
        "reweighing_rate_percentage": (
            (Decimal(reweighed_count) / Decimal(total_weighed) * 100).quantize(Decimal("0.01"))
            if total_weighed else ZERO
        ),
        "underweight_count": deviation_stats["underweight_count"],
        "overweight_count": deviation_stats["overweight_count"],
        "average_deviation": deviation_stats["avg_deviation"],
        "maximum_deviation": deviation_stats["max_deviation"],
        "profile_wise": _grouped(scrap_qs, "profile_id", "profile__name"),
        "work_order_wise": _grouped(scrap_qs, "work_order_id", "work_order__work_order_no"),
        "shift_wise": _grouped(scrap_qs, "shift", "shift"),
        "line_wise": _grouped(scrap_qs, "work_order__extrusion_line_id", "work_order__extrusion_line__name"),
        "reason_wise": _grouped(scrap_qs, "scrap_reason_id", "scrap_reason__name"),
        "category_wise": _grouped(scrap_qs, "scrap_category_id", "scrap_category__name"),
        "stage_wise": _grouped(scrap_qs, "source_stage", "source_stage"),
    }
