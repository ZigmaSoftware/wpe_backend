"""Development-only bootstrap data for admin master navigation."""

from __future__ import annotations

import os

from django.conf import settings
from django.contrib.auth import get_user_model

from .models import MainScreen, ScreenSection, UserScreen


def ensure_dev_full_access_user() -> None:
    if not settings.DEBUG or os.environ.get("BP_SKIP_DEV_BOOTSTRAP") == "1":
        return

    username = os.environ.get("DEV_FULL_ACCESS_USERNAME", "imran").strip()
    password = os.environ.get("DEV_FULL_ACCESS_PASSWORD", "developer")
    email = os.environ.get("DEV_FULL_ACCESS_EMAIL", "")

    if not username or not password:
        return

    user_model = get_user_model()
    user, created = user_model.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )

    needs_save = created
    if user.email != email:
        user.email = email
        needs_save = True
    if not user.is_staff:
        user.is_staff = True
        needs_save = True
    if not user.is_superuser:
        user.is_superuser = True
        needs_save = True
    if not user.is_active:
        user.is_active = True
        needs_save = True
    if created or not user.check_password(password):
        user.set_password(password)
        needs_save = True

    if needs_save:
        user.save()


def ensure_dev_master_data() -> None:
    if not settings.DEBUG or os.environ.get("BP_SKIP_DEV_BOOTSTRAP") == "1":
        return

    ensure_dev_full_access_user()

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
            "screen_name": "User Type Master",
            "code": "user-type-master",
            "section": admin_section,
            "order_no": 4,
        },
        {
            "screen_name": "User Creation Master",
            "code": "user-creation-master",
            "section": admin_section,
            "order_no": 5,
        },
        {
            "screen_name": "User Screen Permission Master",
            "code": "user-screen-permission-master",
            "section": admin_section,
            "order_no": 6,
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
