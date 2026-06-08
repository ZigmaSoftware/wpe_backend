from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.admin_master.models import Staff, UserCreation, UserType
from apps.auth.serializers import CurrentUserSerializer
from apps.wpe_masters.models import DepartmentMaster


User = get_user_model()


class CurrentUserSerializerTests(TestCase):
    def test_exposes_user_type_department_context(self):
        user = User.objects.create_user(username="auth-user", password="test-pass-123")
        staff = Staff.objects.create(name="Auth Staff")
        department = DepartmentMaster.objects.create(name="Compounding")
        user_type = UserType.objects.create(name="Blending User", department=department)
        UserCreation.objects.create(user=user, staff=staff, user_type=user_type)

        data = CurrentUserSerializer(user).data

        self.assertEqual(data["user_type"], user_type.id)
        self.assertEqual(data["user_type_name"], "Blending User")
        self.assertEqual(data["department"], department.id)
        self.assertEqual(data["department_name"], "Compounding")
        self.assertIsNone(data["role"])
        self.assertIsNone(data["role_name"])
