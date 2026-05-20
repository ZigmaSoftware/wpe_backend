from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.admin_master.models import Staff, UserCreation, UserType
from apps.admin_master.services import delete_user_creation_profile
from .models import WPEUserCreation
from .services import delete_wpe_user_creation, upsert_wpe_user_creation


User = get_user_model()


class SharedAuthUserLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="shared-user", password="test-pass-123", email="old@example.com")
        self.staff = Staff.objects.create(name="Shared Staff")
        self.user_type = UserType.objects.create(name="Shared Type")

    def test_wpe_profile_can_share_auth_user_with_admin_profile(self):
        admin_profile = UserCreation.objects.create(user=self.user, staff=self.staff, user_type=self.user_type)

        wpe_profile = upsert_wpe_user_creation(
            username="shared-user",
            full_name="Shared User",
            email="shared@example.com",
            is_active=True,
        )

        self.assertEqual(wpe_profile.user_id, self.user.id)
        self.assertEqual(admin_profile.user_id, self.user.id)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "shared@example.com")

    def test_deleting_one_profile_keeps_shared_auth_user_until_last_profile_is_removed(self):
        admin_profile = UserCreation.objects.create(user=self.user, staff=self.staff, user_type=self.user_type)
        wpe_profile = WPEUserCreation.objects.create(user=self.user, full_name="Shared User")

        delete_wpe_user_creation(wpe_profile)

        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(UserCreation.objects.filter(pk=admin_profile.pk).exists())
        self.assertFalse(WPEUserCreation.objects.filter(pk=wpe_profile.pk).exists())

        delete_user_creation_profile(admin_profile)

        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
