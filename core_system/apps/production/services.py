from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.inventory.models import ProductionInventoryTransaction

from .models import ProductionLineConnection, ProductionLineMaster, ProductionMachine, ProductionOrder

ZERO = Decimal("0.000")


def _normalize_scan_code(value: str | None) -> str:
    return str(value or "").strip()


def _serial_no_from_inventory(row: ProductionInventoryTransaction, fallback: str = "") -> str:
    return (
        str(row.batch_code or "").strip()
        or str(row.reference_no or "").strip()
        or str(row.scan_code or "").strip()
        or str(fallback or "").strip()
    )


def _reference_no_from_inventory(row: ProductionInventoryTransaction, fallback: str = "") -> str:
    return str(row.reference_no or "").strip() or str(row.batch_code or "").strip() or str(fallback or "").strip()


def _production_id_from_inventory(row: ProductionInventoryTransaction) -> str:
    if str(row.production_id or "").strip():
        return str(row.production_id).strip()
    if row.production_order_id and str(row.production_order.production_id or "").strip():
        return str(row.production_order.production_id).strip()
    return ""


def _connection_identity_filters(*, row: ProductionInventoryTransaction, scan_code: str) -> Q:
    query = Q()
    normalized_scan = _normalize_scan_code(scan_code)
    serial_no = _serial_no_from_inventory(row, fallback=normalized_scan)
    reference_no = _reference_no_from_inventory(row, fallback=normalized_scan)

    if row.pk:
        query |= Q(source_inventory_transaction=row)
    if normalized_scan:
        query |= Q(scan_code__iexact=normalized_scan)
    if serial_no:
        query |= Q(serial_no__iexact=serial_no)
    if reference_no:
        query |= Q(reference_no__iexact=reference_no)
    return query


def _connection_queryset():
    return ProductionLineConnection.objects.select_related(
        "production_line",
        "machine",
        "production_order",
        "source_production_order",
        "connected_by",
        "disconnected_by",
        "source_inventory_transaction__production_order",
        "source_inventory_transaction__item",
    )


def get_line_connection_inventory_row(
    scan_code: str,
    *,
    require_available_balance: bool = True,
    for_update: bool = False,
) -> ProductionInventoryTransaction:
    normalized_scan = _normalize_scan_code(scan_code)
    if not normalized_scan:
        raise ValidationError("scan_code is required.")

    queryset = ProductionInventoryTransaction.objects.select_related("item", "production_order", "source_batch")
    if for_update:
        queryset = queryset.select_for_update()

    queryset = queryset.filter(
        stage=ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
    )
    if require_available_balance:
        queryset = queryset.filter(balance_qty__gt=ZERO)

    row = (
        queryset.filter(
            Q(scan_code__iexact=normalized_scan)
            | Q(batch_code__iexact=normalized_scan)
            | Q(reference_no__iexact=normalized_scan)
        )
        .order_by("-updated_at", "-created_at", "-id")
        .first()
    )
    if row is None:
        raise ValidationError("The scanned GL bag is not available in Connection to Line stock.")
    return row


def get_active_line_connection_for_row(
    row: ProductionInventoryTransaction,
    *,
    scan_code: str,
    for_update: bool = False,
) -> ProductionLineConnection | None:
    queryset = _connection_queryset()
    if for_update:
        queryset = queryset.select_for_update()
    return (
        queryset.filter(status=ProductionLineConnection.Status.ON)
        .filter(_connection_identity_filters(row=row, scan_code=scan_code))
        .order_by("-connected_at", "-id")
        .first()
    )


def lookup_line_connection_scan(scan_code: str) -> dict:
    row = get_line_connection_inventory_row(scan_code, require_available_balance=True, for_update=False)
    active_connection = get_active_line_connection_for_row(row, scan_code=scan_code, for_update=False)
    resolved_scan_code = _normalize_scan_code(row.scan_code) or _normalize_scan_code(scan_code)
    return {
        "scan_code": resolved_scan_code,
        "serial_no": _serial_no_from_inventory(row, fallback=resolved_scan_code),
        "reference_no": _reference_no_from_inventory(row, fallback=resolved_scan_code),
        "item_code": str(row.item_code or "").strip(),
        "item_name": str(row.item_name or "").strip(),
        "weight_kg": row.balance_qty,
        "production_id": _production_id_from_inventory(row) or None,
        "is_connected": active_connection is not None,
        "active_connection": active_connection,
    }


def _line_display_name(line: ProductionLineMaster) -> str:
    return str(line.name or line.code or f"Line {line.pk}").strip()


def _connection_line_display_name(connection: ProductionLineConnection) -> str:
    return str(connection.production_line_name or getattr(connection.production_line, "name", "") or "").strip()


def resolve_production_machine(
    *,
    machine_id: int | None = None,
    machine_code: str | None = None,
    machine_name: str | None = None,
) -> ProductionMachine | None:
    queryset = ProductionMachine.objects.filter(is_active=True)
    if machine_id:
        return queryset.filter(pk=machine_id).first()
    if str(machine_code or "").strip():
        return queryset.filter(machine_code__iexact=str(machine_code).strip()).first()
    if str(machine_name or "").strip():
        return queryset.filter(name__iexact=str(machine_name).strip()).first()
    return None


def get_active_line_connection_for_machine(
    *,
    machine_id: int | None = None,
    machine_code: str | None = None,
    machine_name: str | None = None,
    for_update: bool = False,
) -> ProductionLineConnection | None:
    query = Q()
    if machine_id:
        query |= Q(machine_id=machine_id) | Q(production_line__machine_id=machine_id)
    normalized_code = str(machine_code or "").strip()
    if normalized_code:
        query |= Q(machine__machine_code__iexact=normalized_code) | Q(production_line__machine__machine_code__iexact=normalized_code)
    normalized_name = str(machine_name or "").strip()
    if normalized_name:
        query |= (
            Q(machine__name__iexact=normalized_name)
            | Q(machine_name__iexact=normalized_name)
            | Q(production_line__machine__name__iexact=normalized_name)
        )
    if not query:
        return None

    queryset = _connection_queryset()
    if for_update:
        queryset = queryset.select_for_update()
    return (
        queryset.filter(status=ProductionLineConnection.Status.ON)
        .filter(query)
        .order_by("-connected_at", "-id")
        .first()
    )


@transaction.atomic
def connect_scan_to_line(
    *,
    scan_code: str,
    production_line_id: int,
    user=None,
    production_order_id: int | None = None,
) -> ProductionLineConnection:
    row = get_line_connection_inventory_row(scan_code, require_available_balance=True, for_update=True)
    active_connection = get_active_line_connection_for_row(row, scan_code=scan_code, for_update=True)
    if active_connection is not None:
        raise ValidationError(
            f"Bag {active_connection.serial_no} is already connected to "
            f"{_connection_line_display_name(active_connection) or active_connection.production_line_code}."
        )

    line = (
        ProductionLineMaster.objects.select_for_update()
        .select_related("machine")
        .filter(pk=production_line_id, is_active=True)
        .first()
    )
    if line is None:
        raise ValidationError("Selected production line does not exist.")
    if line.status == ProductionLineMaster.LineStatus.MAINTENANCE:
        raise ValidationError(f"{_line_display_name(line)} is under maintenance.")

    line_occupancy = (
        _connection_queryset()
        .select_for_update()
        .filter(production_line=line, status=ProductionLineConnection.Status.ON)
        .order_by("-connected_at", "-id")
        .first()
    )
    if line_occupancy is not None or line.status == ProductionLineMaster.LineStatus.RUNNING:
        raise ValidationError(f"{_line_display_name(line)} is already connected with another bag.")

    production_order = None
    if production_order_id:
        production_order = ProductionOrder.objects.filter(pk=production_order_id).first()

    resolved_scan_code = _normalize_scan_code(row.scan_code) or _normalize_scan_code(scan_code)
    serial_no = _serial_no_from_inventory(row, fallback=resolved_scan_code)
    connection = ProductionLineConnection.objects.create(
        source_inventory_transaction=row,
        production_line=line,
        machine=line.machine,
        production_order=production_order,
        source_production_order=row.production_order,
        item=row.item,
        production_line_name=str(line.name or "").strip(),
        machine_name=str(getattr(line.machine, "name", "") or "").strip(),
        scan_code=resolved_scan_code,
        serial_no=serial_no,
        reference_no=_reference_no_from_inventory(row, fallback=resolved_scan_code),
        item_code=str(row.item_code or "").strip(),
        item_name=str(row.item_name or "").strip(),
        weight_kg=Decimal(str(row.balance_qty or ZERO)),
        status=ProductionLineConnection.Status.ON,
        connected_at=timezone.now(),
        notes="",
        connected_by=user if getattr(user, "is_authenticated", False) else None,
    )

    line.status = ProductionLineMaster.LineStatus.RUNNING
    line.save(update_fields=["status", "updated_at"])
    return connection


@transaction.atomic
def disconnect_line_connection(
    connection: ProductionLineConnection,
    *,
    user=None,
    disconnected_at=None,
) -> ProductionLineConnection:
    locked_connection = (
        _connection_queryset()
        .select_for_update()
        .filter(pk=connection.pk)
        .first()
    )
    if locked_connection is None:
        raise ValidationError("Line connection does not exist.")

    if locked_connection.status != ProductionLineConnection.Status.ON:
        return locked_connection

    locked_connection.status = ProductionLineConnection.Status.OFF
    locked_connection.disconnected_at = disconnected_at or timezone.now()
    locked_connection.disconnected_by = user if getattr(user, "is_authenticated", False) else None
    locked_connection.save(update_fields=["status", "disconnected_at", "disconnected_by", "updated_at"])

    line = locked_connection.production_line
    has_other_active = ProductionLineConnection.objects.select_for_update().filter(
        production_line=line,
        status=ProductionLineConnection.Status.ON,
    ).exclude(pk=locked_connection.pk).exists()
    if not has_other_active and line.status == ProductionLineMaster.LineStatus.RUNNING:
        line.status = ProductionLineMaster.LineStatus.FREE
        line.save(update_fields=["status", "updated_at"])

    return locked_connection


def auto_disconnect_line_connection_for_inventory_row(
    row: ProductionInventoryTransaction,
    *,
    user=None,
) -> ProductionLineConnection | None:
    if Decimal(str(row.balance_qty or ZERO)) > ZERO:
        return None

    active_connection = get_active_line_connection_for_row(
        row,
        scan_code=str(row.scan_code or row.batch_code or row.reference_no or ""),
        for_update=True,
    )
    if active_connection is None:
        return None
    return disconnect_line_connection(active_connection, user=user)
