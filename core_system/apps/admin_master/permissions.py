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

    def _is_self_permission_lookup(self, request, view) -> bool:
        if not getattr(view, "allow_self_permission_lookup", False):
            return False

        if getattr(view, "action", None) not in {"resolved", "menu"}:
            return False

        user_type_id = request.query_params.get("user_type")
        user_id = request.query_params.get("user_id")
        return not user_type_id and not user_id

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        if self._is_self_permission_lookup(request, view):
            return True

        screen_codes = tuple(
            code
            for code in getattr(view, "permission_screen_codes", ())
            if code
        )
        if not screen_codes:
            screen_code = getattr(view, "permission_screen_code", None)
            screen_codes = (screen_code,) if screen_code else ()

        if not screen_codes:
            return True

        action_map = {**self.default_action_map, **getattr(view, "permission_action_map", {})}
        resolved_action = action_map.get(getattr(view, "action", None)) or self.method_fallback_map.get(
            request.method,
            "view",
        )
        return any(
            user_has_screen_action(user, screen_code=screen_code, action=resolved_action)
            for screen_code in screen_codes
        )
