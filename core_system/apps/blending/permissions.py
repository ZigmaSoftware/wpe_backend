from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.admin_master.services import user_has_screen_action
from common.rbac import BLENDING_HEAD_ROLE_TOKENS, BLENDING_ROLE_TOKENS, user_has_role


BLENDING_INVENTORY_VIEW_SCREEN_CODES = ("blending-stock-workspace",)
BLENDING_HEAD_APPROVAL_VIEW_SCREEN_CODES = ("blending-head-approval-workspace",)


def _user_has_any_screen_action(user, screen_codes: tuple[str, ...], actions: tuple[str, ...] = ("list", "view")) -> bool:
    return any(
        user_has_screen_action(user, screen_code=screen_code, action=action)
        for screen_code in screen_codes
        for action in actions
    )


class IsBlendingUser(BasePermission):
    message = "Only blending users can perform this action."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, BLENDING_ROLE_TOKENS)


class IsBlendingHeadUser(BasePermission):
    message = "Only Blending Head users can perform this action."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, BLENDING_HEAD_ROLE_TOKENS)


class IsBlendingInventoryViewer(BasePermission):
    message = "You do not have permission to view blending inventory."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, BLENDING_ROLE_TOKENS) or _user_has_any_screen_action(
            request.user,
            BLENDING_INVENTORY_VIEW_SCREEN_CODES,
        )


class IsBlendingHeadApprovalViewer(BasePermission):
    message = "You do not have permission to view blending head approvals."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, BLENDING_HEAD_ROLE_TOKENS) or _user_has_any_screen_action(
            request.user,
            BLENDING_HEAD_APPROVAL_VIEW_SCREEN_CODES,
        )
