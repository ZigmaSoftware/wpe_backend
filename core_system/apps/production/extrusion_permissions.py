"""DRF permission classes for the Extrusion Production / Packing / Weight
Verification / Sticker Generation / Scrap KPI module, mirroring
`apps.store.permissions`.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.admin_master.services import user_has_screen_action
from common.rbac import (
    EXTRUSION_ALL_ROLE_TOKENS,
    EXTRUSION_PACKING_OPERATOR_ROLE_TOKENS,
    EXTRUSION_PRODUCTION_ROLE_TOKENS,
    EXTRUSION_QC_APPROVER_ROLE_TOKENS,
    EXTRUSION_QUALITY_INSPECTOR_ROLE_TOKENS,
    EXTRUSION_SUPERVISOR_ROLE_TOKENS,
    EXTRUSION_WAREHOUSE_ROLE_TOKENS,
    EXTRUSION_WEIGHING_OPERATOR_ROLE_TOKENS,
    user_has_role,
)


WORK_ORDER_SCREEN_CODES = ("production-extrusion-workorder-workspace",)
INSPECTION_SCREEN_CODES = ("production-extrusion-inspection-workspace",)
PACKING_SCREEN_CODES = ("production-extrusion-packing-workspace",)
WEIGHING_SCREEN_CODES = ("production-extrusion-weighing-workspace",)
STICKER_SCREEN_CODES = ("production-extrusion-sticker-workspace",)
SHIFT_APPROVAL_SCREEN_CODES = ("production-extrusion-shift-approval-workspace",)
SCRAP_SCREEN_CODES = ("production-extrusion-scrap-workspace",)
WAREHOUSE_SCREEN_CODES = ("production-extrusion-warehouse-workspace",)
KPI_SCREEN_CODES = ("production-extrusion-kpi-dashboard",)


def _has_any_screen_action(user, screen_codes: tuple[str, ...], actions: tuple[str, ...] = ("list", "view")) -> bool:
    return any(
        user_has_screen_action(user, screen_code=screen_code, action=action)
        for screen_code in screen_codes
        for action in actions
    )


def _role_or_screen(user, role_tokens: set[str], screen_codes: tuple[str, ...]) -> bool:
    return user_has_role(user, role_tokens) or _has_any_screen_action(user, screen_codes)


class IsExtrusionUser(BasePermission):
    message = "Only extrusion module users can perform this action."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, EXTRUSION_ALL_ROLE_TOKENS)


class IsExtrusionProductionUser(BasePermission):
    message = "Only production users can manage extrusion work orders."

    def has_permission(self, request, view) -> bool:
        return _role_or_screen(request.user, EXTRUSION_PRODUCTION_ROLE_TOKENS, WORK_ORDER_SCREEN_CODES)


class IsExtrusionQualityInspector(BasePermission):
    message = "Only quality inspectors can record extrusion inspections."

    def has_permission(self, request, view) -> bool:
        return _role_or_screen(request.user, EXTRUSION_QUALITY_INSPECTOR_ROLE_TOKENS, INSPECTION_SCREEN_CODES)


class IsExtrusionPackingOperator(BasePermission):
    message = "Only packing operators can create packets."

    def has_permission(self, request, view) -> bool:
        return _role_or_screen(request.user, EXTRUSION_PACKING_OPERATOR_ROLE_TOKENS, PACKING_SCREEN_CODES)


class IsExtrusionWeighingOperator(BasePermission):
    message = "Only weighing operators can capture packet weight."

    def has_permission(self, request, view) -> bool:
        return _role_or_screen(request.user, EXTRUSION_WEIGHING_OPERATOR_ROLE_TOKENS, WEIGHING_SCREEN_CODES)


class IsExtrusionQCApprover(BasePermission):
    message = "Only QC approvers can perform shift-end approval."

    def has_permission(self, request, view) -> bool:
        return _role_or_screen(request.user, EXTRUSION_QC_APPROVER_ROLE_TOKENS, SHIFT_APPROVAL_SCREEN_CODES)


class IsExtrusionWarehouseUser(BasePermission):
    message = "Only warehouse users can receive packets."

    def has_permission(self, request, view) -> bool:
        return _role_or_screen(request.user, EXTRUSION_WAREHOUSE_ROLE_TOKENS, WAREHOUSE_SCREEN_CODES)


class IsExtrusionSupervisor(BasePermission):
    """Gate for authorized overrides / reversals — Supervisor / Administrator only."""

    message = "Only a supervisor or administrator can perform this action."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, EXTRUSION_SUPERVISOR_ROLE_TOKENS)


class IsExtrusionStickerOperator(BasePermission):
    """Sticker generation/scan follows on directly from packing or weighing."""

    message = "Only packing, weighing or supervisor users can generate or scan stickers."

    def has_permission(self, request, view) -> bool:
        combined_tokens = (
            EXTRUSION_PACKING_OPERATOR_ROLE_TOKENS
            | EXTRUSION_WEIGHING_OPERATOR_ROLE_TOKENS
            | EXTRUSION_SUPERVISOR_ROLE_TOKENS
        )
        return _role_or_screen(request.user, combined_tokens, PACKING_SCREEN_CODES + WEIGHING_SCREEN_CODES)


class IsExtrusionScrapUser(BasePermission):
    """Scrap can be raised from QC inspection, packing, weighing or shift-end QC."""

    message = "You do not have permission to record extrusion scrap."

    def has_permission(self, request, view) -> bool:
        combined_tokens = (
            EXTRUSION_QUALITY_INSPECTOR_ROLE_TOKENS
            | EXTRUSION_PACKING_OPERATOR_ROLE_TOKENS
            | EXTRUSION_WEIGHING_OPERATOR_ROLE_TOKENS
            | EXTRUSION_QC_APPROVER_ROLE_TOKENS
            | EXTRUSION_SUPERVISOR_ROLE_TOKENS
        )
        return _role_or_screen(request.user, combined_tokens, SCRAP_SCREEN_CODES)


class IsExtrusionKPIViewer(BasePermission):
    message = "You do not have permission to view the extrusion KPI dashboard."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, EXTRUSION_ALL_ROLE_TOKENS) or _has_any_screen_action(
            request.user, KPI_SCREEN_CODES
        )
