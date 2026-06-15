from __future__ import annotations

from rest_framework.permissions import BasePermission

from common.rbac import BLENDING_HEAD_ROLE_TOKENS, BLENDING_ROLE_TOKENS, user_has_role


class IsBlendingUser(BasePermission):
    message = "Only blending users can perform this action."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, BLENDING_ROLE_TOKENS)


class IsBlendingHeadUser(BasePermission):
    message = "Only Blending Head users can perform this action."

    def has_permission(self, request, view) -> bool:
        return user_has_role(request.user, BLENDING_HEAD_ROLE_TOKENS)
