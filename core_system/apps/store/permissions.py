from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.admin_master.services import user_has_screen_action
from common.rbac import STORE_ROLE_TOKENS, user_has_role


STORE_INVENTORY_VIEW_SCREEN_CODES = (
    "inventory-store-inventory-workspace",
    "store-stock-workspace",
)
STORE_REQUEST_VIEW_SCREEN_CODES = ("store-request-workspace",)
STORE_DASHBOARD_VIEW_SCREEN_CODES = STORE_INVENTORY_VIEW_SCREEN_CODES


def _user_has_any_screen_action(user, screen_codes: tuple[str, ...], actions: tuple[str, ...] = ("list", "view")) -> bool:
    return any(
        user_has_screen_action(user, screen_code=screen_code, action=action)
        for screen_code in screen_codes
        for action in actions
    )


class IsStoreUser(BasePermission):
    message = "Only store users can perform this action."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, STORE_ROLE_TOKENS)


class IsStoreInventoryViewer(BasePermission):
    message = "You do not have permission to view store inventory."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, STORE_ROLE_TOKENS) or _user_has_any_screen_action(
            request.user,
            STORE_INVENTORY_VIEW_SCREEN_CODES,
        )


class IsStoreRequestViewer(BasePermission):
    message = "You do not have permission to view store requests."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, STORE_ROLE_TOKENS) or _user_has_any_screen_action(
            request.user,
            STORE_REQUEST_VIEW_SCREEN_CODES,
        )


class IsStoreDashboardViewer(BasePermission):
    message = "You do not have permission to view store dashboard data."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, STORE_ROLE_TOKENS) or _user_has_any_screen_action(
            request.user,
            STORE_DASHBOARD_VIEW_SCREEN_CODES,
        )
