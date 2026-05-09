from __future__ import annotations

import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .bootstrap import ensure_dev_full_access_user
from .models import MainScreen, ScreenSection, UserScreen
from .services import resolve_subject_permissions


User = get_user_model()


class DevFullAccessUserBootstrapTests(TestCase):
    @override_settings(DEBUG=True)
    @mock.patch.dict(
        os.environ,
        {
            "DEV_FULL_ACCESS_USERNAME": "imran",
            "DEV_FULL_ACCESS_PASSWORD": "developer",
            "DEV_FULL_ACCESS_EMAIL": "imran@example.com",
        },
        clear=False,
    )
    def test_creates_full_access_user_when_missing(self):
        ensure_dev_full_access_user()

        user = User.objects.get(username="imran")
        self.assertEqual(user.email, "imran@example.com")
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("developer"))


class FullAccessPermissionResolutionTests(TestCase):
    def test_superuser_receives_full_menu_permissions_without_admin_profile(self):
        main_screen = MainScreen.objects.create(name="Operations", code="operations", order_no=1, status=True)
        section = ScreenSection.objects.create(
            main_screen=main_screen,
            name="Production",
            code="production",
            order_no=1,
            is_active=True,
        )
        UserScreen.objects.create(
            main_screen=main_screen,
            screen_section=section,
            screen_name="Store",
            code="store-screen",
            folder_name="store",
            order_no=1,
            is_active=True,
            available_actions=["list", "view", "update"],
        )
        user = User.objects.create_user(
            username="imran",
            password="developer",
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )

        data = resolve_subject_permissions(user=user)

        self.assertEqual(data["user_type"]["code"], "full-access")
        self.assertEqual(len(data["menu"]), 1)
        screen = data["menu"][0]["sections"][0]["screens"][0]
        self.assertTrue(screen["action_permissions"]["all"])
        self.assertTrue(screen["action_permissions"]["list"])
        self.assertTrue(screen["action_permissions"]["view"])
        self.assertTrue(screen["action_permissions"]["update"])
        self.assertFalse(screen["action_permissions"]["delete"])

    @override_settings(DEBUG=True)
    @mock.patch.dict(
        os.environ,
        {
            "DEV_FULL_ACCESS_USERNAME": "imran",
            "DEV_FULL_ACCESS_PASSWORD": "developer",
            "DEV_FULL_ACCESS_EMAIL": "imran@example.com",
        },
        clear=False,
    )
    def test_upgrades_existing_user_to_full_access(self):
        user = User.objects.create_user(
            username="imran",
            password="old-password",
            email="old@example.com",
            is_active=False,
        )

        ensure_dev_full_access_user()

        user.refresh_from_db()
        self.assertEqual(user.email, "imran@example.com")
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("developer"))
