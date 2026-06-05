from __future__ import annotations

import os
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .bootstrap import ensure_dev_full_access_user
from .models import (
    MainScreen,
    Role,
    ScreenSection,
    Staff,
    UserCreation,
    UserScreen,
    UserType,
    UserTypePermission,
)
from .serializers import StaffSerializer, UserCreationWriteSerializer
from .services import delete_user_creation, resolve_subject_permissions
from apps.common_master.models import Company
from apps.login_home.models import Department
from apps.wpe_masters.models import DepartmentMaster, RoleMaster, WPEUserCreation


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


class StaffSerializerTests(TestCase):
    def test_creates_staff_with_extended_fields(self):
        serializer = StaffSerializer(
            data={
                "staff_code": "EMP-001",
                "name": "Ravi Kumar",
                "age": 29,
                "designation": "Supervisor",
                "mobile": "9876543210",
                "email": "ravi@example.com",
                "joining_date": "2026-06-01",
                "gender": Staff.Gender.MALE,
                "address": "Chennai",
                "emergency_contact_no": "9123456789",
                "is_active": True,
                "remarks": "Night shift",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        staff = serializer.save()

        self.assertEqual(staff.staff_code, "EMP-001")
        self.assertEqual(staff.name, "Ravi Kumar")
        self.assertEqual(staff.age, 29)
        self.assertEqual(staff.designation, "Supervisor")
        self.assertEqual(staff.mobile, "9876543210")
        self.assertEqual(staff.email, "ravi@example.com")
        self.assertEqual(staff.joining_date, date(2026, 6, 1))
        self.assertEqual(staff.gender, Staff.Gender.MALE)
        self.assertEqual(staff.address, "Chennai")
        self.assertEqual(staff.emergency_contact_no, "9123456789")
        self.assertTrue(staff.is_active)
        self.assertEqual(staff.remarks, "Night shift")

    def test_requires_employee_id_and_contact_fields(self):
        serializer = StaffSerializer(
            data={
                "staff_code": "",
                "name": "Ravi Kumar",
                "age": 29,
                "designation": "",
                "mobile": "",
                "email": "",
                "is_active": True,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("staff_code", serializer.errors)
        self.assertIn("designation", serializer.errors)
        self.assertIn("mobile", serializer.errors)
        self.assertIn("email", serializer.errors)


class UserCreationDeletionTests(TestCase):
    def test_deletes_user_creation_even_when_auth_user_is_shared_with_wpe_profile(self):
        user = User.objects.create_user(username="delete-me", password="secret123")
        staff = Staff.objects.create(name="Delete Me")
        profile = UserCreation.objects.create(user=user, staff=staff)
        wpe_profile = WPEUserCreation.objects.create(
            user=user,
            full_name="Delete Me",
            email="delete@example.com",
        )

        delete_user_creation(profile)

        self.assertFalse(UserCreation.objects.filter(pk=profile.pk).exists())
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertTrue(WPEUserCreation.objects.filter(pk=wpe_profile.pk).exists())

    def test_deletes_linked_auth_user_when_no_other_profiles_reference_it(self):
        user = User.objects.create_user(username="delete-orphan", password="secret123")
        staff = Staff.objects.create(name="Delete Orphan")
        profile = UserCreation.objects.create(user=user, staff=staff)

        delete_user_creation(profile)

        self.assertFalse(UserCreation.objects.filter(pk=profile.pk).exists())
        self.assertFalse(User.objects.filter(pk=user.pk).exists())


class UserCreationWriteSerializerTests(TestCase):
    def test_allows_password_similar_to_username_and_creates_role_based_login(self):
        legacy_department = Department.objects.create(name="Admin")
        legacy_role = Role.objects.create(name="Admin")
        department_master = DepartmentMaster.objects.create(name="Admin")
        role_master = RoleMaster.objects.create(name="Admin")
        user_type = UserType.objects.create(
            name="",
            department=department_master,
            role=role_master,
        )
        company = Company.objects.create(name="Zigma", code="COMP999")
        staff = Staff.objects.create(
            staff_code="968",
            name="Mohamed Imran",
            mobile="8667243299",
            email="mohamed.imran30.dev@gmail.com",
            department_master=department_master,
            role_master=role_master,
        )
        main_screen = MainScreen.objects.create(
            name="Masters",
            code="masters",
            order_no=1,
            status=True,
        )
        section = ScreenSection.objects.create(
            main_screen=main_screen,
            name="Admin Master",
            code="admin-master",
            order_no=1,
            is_active=True,
        )
        screen = UserScreen.objects.create(
            main_screen=main_screen,
            screen_section=section,
            screen_name="User Creation",
            code="user-creation",
            folder_name="/admin/user-creation",
            order_no=1,
            is_active=True,
            available_actions=["add", "list", "view"],
        )
        UserTypePermission.objects.create(
            user_type=user_type,
            main_screen=main_screen,
            screen_section=section,
            user_screen=screen,
            scope_type=UserTypePermission.ScopeType.SCREEN,
            action_permissions={
                "all": False,
                "add": True,
                "update": False,
                "list": True,
                "delete": False,
                "view": True,
                "print": False,
            },
            status=True,
        )

        serializer = UserCreationWriteSerializer(
            data={
                "staff": staff.id,
                "user_type": user_type.id,
                "company": company.id,
                "username": "imran",
                "password": "imran123",
                "confirm_password": "imran123",
                "mobile_no": "8667243299",
                "email": "mohamed.imran30.dev@gmail.com",
                "account_status": UserCreation.AccountStatus.ACTIVE,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        profile = serializer.save()

        self.assertEqual(profile.user.username, "imran")
        self.assertTrue(profile.user.check_password("imran123"))
        self.assertEqual(profile.user_type_id, user_type.id)
        self.assertEqual(profile.company_id, company.id)
        self.assertEqual(profile.department_id, legacy_department.id)
        self.assertEqual(profile.role_id, legacy_role.id)

        permissions = resolve_subject_permissions(user=profile.user)
        self.assertEqual(permissions["user_type"]["id"], user_type.id)
        screen_permissions = permissions["menu"][0]["sections"][0]["screens"][0]["action_permissions"]
        self.assertTrue(screen_permissions["add"])
        self.assertTrue(screen_permissions["list"])
        self.assertTrue(screen_permissions["view"])
        self.assertFalse(screen_permissions["delete"])
