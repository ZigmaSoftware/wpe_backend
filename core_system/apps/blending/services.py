from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.store.models import StockRequest, StoreStock
from apps.store.services import (
    cancel_store_request,
    create_store_request,
    get_blending_warehouse,
    get_store_warehouse,
    normalize_text,
    update_store_request,
)


BLENDING_DEPARTMENT = "BLENDING"


def is_additive_item(item) -> bool:
    # Legacy helper kept for backward compatibility. Blending requests are no
    # longer restricted to additive-tagged items.
    return True


def additive_item_query() -> Q:
    # Legacy helper kept for backward compatibility. Requestable stock now
    # includes all available store stock items.
    return Q()


def resolve_blending_request_department(user, fallback: str = BLENDING_DEPARTMENT) -> str:
    profile = getattr(user, "admin_profile", None)
    user_type = getattr(profile, "user_type", None)
    user_type_department = getattr(user_type, "department", None)
    department_name = normalize_text(getattr(user_type_department, "name", None))
    if department_name:
        return department_name

    legacy_department = getattr(profile, "department", None)
    department_name = normalize_text(getattr(legacy_department, "name", None))
    if department_name:
        return department_name

    staff = getattr(profile, "staff", None)
    staff_department = getattr(staff, "department_master", None)
    department_name = normalize_text(getattr(staff_department, "name", None))
    if department_name:
        return department_name

    return normalize_text(fallback) or BLENDING_DEPARTMENT


def create_blending_store_request(
    *,
    requested_by,
    items,
    remarks=None,
    request_type="GENERAL",
    department=BLENDING_DEPARTMENT,
    request_date=None,
    require_date=None,
    require_time=None,
    requested_for_name="",
    request_reason="",
):
    return create_store_request(
        requested_by=requested_by,
        items=items,
        remarks=remarks,
        request_type=request_type,
        department=department,
        request_date=request_date,
        require_date=require_date,
        require_time=require_time,
        requested_for_name=requested_for_name,
        request_reason=request_reason,
    )


def cancel_blending_store_request(request_id: int, cancelled_by, remarks: str | None = None):
    return cancel_store_request(request_id, cancelled_by, remarks=remarks)


def update_blending_store_request(
    request_id: int,
    *,
    requested_by,
    items,
    remarks=None,
    request_type="GENERAL",
    department=BLENDING_DEPARTMENT,
    request_date=None,
    require_date=None,
    require_time=None,
    requested_for_name="",
    request_reason="",
):
    return update_store_request(
        request_id,
        requested_by=requested_by,
        items=items,
        remarks=remarks,
        request_type=request_type,
        department=department,
        request_date=request_date,
        require_date=require_date,
        require_time=require_time,
        requested_for_name=requested_for_name,
        request_reason=request_reason,
    )


def _review_blending_store_request(
    request_id: int,
    *,
    head_user,
    target_status: str,
    remarks: str | None = None,
):
    with transaction.atomic():
        try:
            stock_request = (
                StockRequest.objects.select_for_update()
                .select_related("head_action_by")
                .prefetch_related("items__item")
                .get(pk=request_id)
            )
        except StockRequest.DoesNotExist as exc:
            raise ValidationError({"detail": "Blending store request was not found."}) from exc

        if stock_request.status != StockRequest.Status.PENDING_HEAD_APPROVAL:
            raise ValidationError({"status": "Only requests pending Blending Head approval can be reviewed."})

        stock_request.status = target_status
        stock_request.head_action_by = head_user
        stock_request.head_action_at = timezone.now()
        stock_request.head_approval_remarks = normalize_text(remarks) or None
        stock_request.save(
            update_fields=[
                "status",
                "head_action_by",
                "head_action_at",
                "head_approval_remarks",
            ]
        )

    return stock_request


def approve_blending_store_request_by_head(request_id: int, *, head_user, remarks: str | None = None):
    return _review_blending_store_request(
        request_id,
        head_user=head_user,
        target_status=StockRequest.Status.PENDING_STORE_ISSUE,
        remarks=remarks,
    )


def reject_blending_store_request_by_head(request_id: int, *, head_user, remarks: str | None = None):
    return _review_blending_store_request(
        request_id,
        head_user=head_user,
        target_status=StockRequest.Status.HEAD_REJECTED,
        remarks=remarks,
    )


def blending_stock_queryset():
    blending_warehouse = get_blending_warehouse()
    return (
        StoreStock.objects.select_related("item", "warehouse")
        .filter(warehouse=blending_warehouse, available_qty__gt=0)
        .order_by("item__item_name", "id")
    )


def requestable_additive_stock_queryset():
    store_warehouse = get_store_warehouse()
    return (
        StoreStock.objects.select_related("item", "warehouse")
        .filter(warehouse=store_warehouse)
        .order_by("item__item_name", "id")
    )
