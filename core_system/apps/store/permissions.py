from __future__ import annotations

from rest_framework.permissions import BasePermission

from common.rbac import STORE_ROLE_TOKENS, user_has_role


class IsStoreUser(BasePermission):
    message = "Only store users can perform this action."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, STORE_ROLE_TOKENS)
