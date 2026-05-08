"""Validation helpers for admin master serializers and services."""

from __future__ import annotations

import re

from rest_framework import serializers

from .models import PERMISSION_ACTIONS, SCREEN_ACTIONS, default_action_permissions


MOBILE_NUMBER_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")


def validate_mobile_number(value: str | None) -> str | None:
    if value in (None, ""):
        return None

    normalized = str(value).replace(" ", "").strip()
    if not MOBILE_NUMBER_PATTERN.match(normalized):
        raise serializers.ValidationError("Enter a valid mobile number with 10 to 15 digits.")

    return normalized.lstrip("+")


def normalize_screen_actions(value) -> list[str]:
    if value in (None, "", []):
        return list(SCREEN_ACTIONS)

    if not isinstance(value, (list, tuple, set)):
        raise serializers.ValidationError("Available actions must be a list of action names.")

    actions: list[str] = []
    seen: set[str] = set()

    for item in value:
        action = str(item).strip().lower()
        if action not in SCREEN_ACTIONS:
            raise serializers.ValidationError(f"Unsupported screen action: {action}")
        if action not in seen:
            seen.add(action)
            actions.append(action)

    return actions


def normalize_action_permissions(value, *, available_actions=None) -> dict[str, bool]:
    normalized = default_action_permissions()
    allowed_actions = tuple(available_actions or SCREEN_ACTIONS)

    if value in (None, "", {}):
        return normalized

    if isinstance(value, (list, tuple, set)):
        requested_actions = {str(item).strip().lower() for item in value if str(item).strip()}
        invalid_actions = sorted(requested_actions.difference(PERMISSION_ACTIONS))
        if invalid_actions:
            raise serializers.ValidationError(
                f"Unsupported permission actions: {', '.join(invalid_actions)}"
            )

        if "all" in requested_actions:
            normalized["all"] = True
            for action in allowed_actions:
                normalized[action] = True
            return normalized

        for action in allowed_actions:
            normalized[action] = action in requested_actions
        return normalized

    if not isinstance(value, dict):
        raise serializers.ValidationError("Action permissions must be an object or list.")

    invalid_actions = sorted(
        str(key).strip().lower()
        for key in value.keys()
        if str(key).strip().lower() not in PERMISSION_ACTIONS
    )
    if invalid_actions:
        raise serializers.ValidationError(
            f"Unsupported permission actions: {', '.join(invalid_actions)}"
        )

    for action in PERMISSION_ACTIONS:
        normalized[action] = bool(value.get(action, False))

    if normalized["all"]:
        for action in allowed_actions:
            normalized[action] = True

    return normalized


def validate_scope_relationship(*, main_screen=None, screen_section=None, user_screen=None) -> None:
    if screen_section and main_screen and screen_section.main_screen_id != main_screen.id:
        raise serializers.ValidationError(
            {"screen_section": "Selected section does not belong to the selected main screen."}
        )

    if user_screen:
        if main_screen and user_screen.main_screen_id != main_screen.id:
            raise serializers.ValidationError(
                {"user_screen": "Selected screen does not belong to the selected main screen."}
            )
        if screen_section and user_screen.screen_section_id != screen_section.id:
            raise serializers.ValidationError(
                {"user_screen": "Selected screen does not belong to the selected section."}
            )


def has_any_granted_action(action_permissions: dict[str, bool], *, available_actions=None) -> bool:
    allowed_actions = tuple(available_actions or SCREEN_ACTIONS)
    if action_permissions.get("all"):
        return True
    return any(bool(action_permissions.get(action)) for action in allowed_actions)
