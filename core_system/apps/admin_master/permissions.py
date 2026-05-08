"""Dynamic permission classes for admin master RBAC."""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from .services import user_has_screen_action


class AdminMasterRBACPermission(BasePermission):
    message = "You do not have permission to perform this action."

    default_action_map = {
        "list": "list",
        "retrieve": "view",
        "create": "add",
        "update": "update",
        "partial_update": "update",
        "destroy": "delete",
        "toggle_status": "update",
        "assign": "update",
        "resolved": "view",
        "menu": "view",
        "lookup": "view",
    }

    method_fallback_map = {
        "GET": "view",
        "POST": "add",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        screen_code = getattr(view, "permission_screen_code", None)
        if not screen_code:
            return True

        action_map = {**self.default_action_map, **getattr(view, "permission_action_map", {})}
        resolved_action = action_map.get(getattr(view, "action", None)) or self.method_fallback_map.get(
            request.method,
            "view",
        )
        return user_has_screen_action(user, screen_code=screen_code, action=resolved_action)
