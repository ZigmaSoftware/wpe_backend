"""Development-only bootstrap data for admin master navigation."""

from __future__ import annotations

import os

from django.conf import settings

from .models import MainScreen, ScreenSection, UserScreen


def ensure_dev_master_data() -> None:
    if not settings.DEBUG or os.environ.get("BP_SKIP_DEV_BOOTSTRAP") == "1":
        return

    masters_screen, _ = MainScreen.objects.get_or_create(
        name="Masters",
        defaults={"code": "masters", "order_no": 1, "status": True},
    )

    admin_section, _ = ScreenSection.objects.get_or_create(
        name="Admin Master",
        main_screen=masters_screen,
        defaults={"code": "admin-master", "order_no": 1, "is_active": True},
    )

    common_section, _ = ScreenSection.objects.get_or_create(
        name="Common Master",
        main_screen=masters_screen,
        defaults={"code": "common-master", "order_no": 2, "is_active": True},
    )

    hr_section, _ = ScreenSection.objects.get_or_create(
        name="HR Master",
        main_screen=masters_screen,
        defaults={"code": "hr-master", "order_no": 3, "is_active": True},
    )

    dev_screens = (
        {
            "screen_name": "Main Screen Master",
            "code": "main-screen-master",
            "section": admin_section,
            "order_no": 1,
        },
        {
            "screen_name": "Screen Section Master",
            "code": "screen-section-master",
            "section": admin_section,
            "order_no": 2,
        },
        {
            "screen_name": "User Screen Master",
            "code": "user-screen-master",
            "section": admin_section,
            "order_no": 3,
        },
        {
            "screen_name": "Staff Master",
            "code": "staff-master",
            "section": hr_section,
            "order_no": 4,
        },
        {
            "screen_name": "User Type Master",
            "code": "user-type-master",
            "section": admin_section,
            "order_no": 5,
        },
        {
            "screen_name": "User Account Master",
            "code": "user-account-master",
            "section": admin_section,
            "order_no": 6,
        },
        {
            "screen_name": "User Permission Master",
            "code": "user-permission-master",
            "section": admin_section,
            "order_no": 7,
        },
    )

    for screen in dev_screens:
        UserScreen.objects.get_or_create(
            code=screen["code"],
            defaults={
                "main_screen": masters_screen,
                "screen_section": screen["section"],
                "screen_name": screen["screen_name"],
                "folder_name": screen["code"],
                "order_no": screen["order_no"],
                "is_active": True,
                "available_actions": ["add", "update", "list", "delete", "view", "print"],
            },
        )

    _ = common_section
