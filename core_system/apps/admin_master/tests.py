from __future__ import annotations

import os
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

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
from .serializers import StaffSerializer, UserCreationReadSerializer, UserCreationWriteSerializer
from .services import delete_user_creation, resolve_subject_permissions
from .views import StaffViewSet
from apps.common_master.models import Company
from apps.login_home.models import Department
from apps.wpe_masters.models import DepartmentMaster, DesignationMaster, RoleMaster, WPEUserCreation


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
        main_screen = MainScreen.objects.create(name="Operations-Test", code="operations-test", order_no=1, status=True)
        section = ScreenSection.objects.create(
            main_screen=main_screen,
            name="Production-Test",
            code="production-test",
            order_no=1,
            is_active=True,
        )
        test_screen = UserScreen.objects.create(
            main_screen=main_screen,
            screen_section=section,
            screen_name="Store-Test",
            code="store-screen-test",
            folder_name="store",
            order_no=1,
            is_active=True,
            available_actions=["list", "view", "update"],
        )
        user = User.objects.create_user(
            username="imran-test",
            password="developer1",
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )

        data = resolve_subject_permissions(user=user)

        self.assertEqual(data["user_type"]["code"], "full-access")
        self.assertGreater(len(data["menu"]), 1)
        found = False
        for main in data["menu"]:
            for sec in main["sections"]:
                for screen in sec["screens"]:
                    if screen["id"] == test_screen.id:
                        found = True
                        self.assertTrue(screen["action_permissions"]["all"])
                        self.assertTrue(screen["action_permissions"]["list"])
                        self.assertTrue(screen["action_permissions"]["view"])
                        self.assertTrue(screen["action_permissions"]["update"])
                        self.assertFalse(screen["action_permissions"]["delete"])
        self.assertTrue(found, "Test screen should be in the full access menu")

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
    def test_rejects_duplicate_employee_id_and_phone_number(self):
        Staff.objects.create(
            staff_code="EMP-001",
            name="Existing Staff",
            mobile="9876543210",
        )

        serializer = StaffSerializer(
            data={
                "staff_code": " emp-001 ",
                "name": "Duplicate Staff",
                "age": 30,
                "mobile": "9876543210",
                "email": "duplicate@example.com",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(str(serializer.errors["staff_code"][0]), "Employee ID already exists.")
        self.assertEqual(str(serializer.errors["mobile"][0]), "Phone no already exists.")

    def test_duplicate_checks_allow_current_staff_values_on_edit(self):
        staff = Staff.objects.create(
            staff_code="EMP-001",
            name="Existing Staff",
            mobile="9876543210",
        )
        serializer = StaffSerializer(instance=staff)

        self.assertEqual(serializer.validate_staff_code(" EMP-001 "), "EMP-001")
        self.assertEqual(serializer.validate_mobile("9876543210"), "9876543210")

    def test_creates_staff_with_extended_fields(self):
        department_master = DepartmentMaster.objects.create(name="Administration")
        designation_master = DesignationMaster.objects.create(
            name="Supervisor",
            department=department_master,
        )
        serializer = StaffSerializer(
            data={
                "staff_code": "EMP-001",
                "name": "Ravi Kumar",
                "age": 29,
                "designation": designation_master.id,
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
        self.assertEqual(staff.department_master_id, department_master.id)
        self.assertEqual(staff.designation_master_id, designation_master.id)
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
                "designation": 0,
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


class StaffViewSetActionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="staff-admin", password="secret123", is_active=True)
        self.factory = APIRequestFactory(HTTP_HOST="127.0.0.1:8000")

    def test_toggle_status_updates_staff_linked_user_creation_and_auth_user(self):
        staff = Staff.objects.create(name="Status User", is_active=True)
        auth_user = User.objects.create_user(username="status-user", password="secret123", is_active=True)
        profile = UserCreation.objects.create(
            user=auth_user,
            staff=staff,
            account_status=UserCreation.AccountStatus.ACTIVE,
        )

        request = self.factory.patch(f"/api/users/staff/{staff.id}/toggle-status/", {})
        force_authenticate(request, user=self.user)
        response = StaffViewSet.as_view({"patch": "toggle_status"})(request, pk=staff.id)

        staff.refresh_from_db()
        profile.refresh_from_db()
        auth_user.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(staff.is_active)
        self.assertEqual(profile.account_status, UserCreation.AccountStatus.INACTIVE)
        self.assertFalse(profile.is_active)
        self.assertFalse(auth_user.is_active)

    def test_destroy_removes_linked_user_creation_before_deleting_staff(self):
        staff = Staff.objects.create(name="Delete Staff")
        auth_user = User.objects.create_user(username="delete-staff-user", password="secret123", is_active=True)
        profile = UserCreation.objects.create(
            user=auth_user,
            staff=staff,
            account_status=UserCreation.AccountStatus.ACTIVE,
        )

        request = self.factory.delete(f"/api/users/staff/{staff.id}/")
        force_authenticate(request, user=self.user)
        response = StaffViewSet.as_view({"delete": "destroy"})(request, pk=staff.id)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserCreation.objects.filter(pk=profile.pk).exists())
        self.assertFalse(Staff.objects.filter(pk=staff.pk).exists())
        self.assertFalse(User.objects.filter(pk=auth_user.pk).exists())


class UserCreationWriteSerializerTests(TestCase):
    def test_allows_password_similar_to_username_and_creates_role_based_login(self):
        legacy_department, _ = Department.objects.get_or_create(name="Admin-Test")
        legacy_role, _ = Role.objects.get_or_create(name="Admin-Test")
        department_master, _ = DepartmentMaster.objects.get_or_create(name="Admin-Test")
        role_master, _ = RoleMaster.objects.get_or_create(name="Admin-Test")
        user_type = UserType.objects.create(
            name="Test User Type",
            department=department_master,
            role=role_master,
        )
        company = Company.objects.create(name="Zigma-Test", code="COMP999")
        staff = Staff.objects.create(
            staff_code="968",
            name="Mohamed Imran",
            mobile="8667243299",
            email="mohamed.imran30.dev@gmail.com",
            department_master=department_master,
            role_master=role_master,
        )
        main_screen = MainScreen.objects.create(
            name="Masters-Test",
            code="masters-test",
            order_no=1,
            status=True,
        )
        section = ScreenSection.objects.create(
            main_screen=main_screen,
            name="Admin Master-Test",
            code="admin-master-test",
            order_no=1,
            is_active=True,
        )
        screen = UserScreen.objects.create(
            main_screen=main_screen,
            screen_section=section,
            screen_name="User Creation",
            code="user-creation-test",
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
        self.assertEqual(profile.password, "imran123")
        self.assertEqual(UserCreationReadSerializer(profile).data["password"], "imran123")
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
