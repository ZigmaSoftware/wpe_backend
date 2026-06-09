from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


User = get_user_model()


class CurrentUserSerializer(serializers.ModelSerializer):
    user_type = serializers.SerializerMethodField()
    user_type_name = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()

    def _get_profile(self, obj):
        return getattr(obj, "admin_profile", None)

    def _get_user_type(self, obj):
        profile = self._get_profile(obj)
        return getattr(profile, "user_type", None)

    def get_user_type(self, obj):
        user_type = self._get_user_type(obj)
        return getattr(user_type, "id", None)

    def get_user_type_name(self, obj):
        user_type = self._get_user_type(obj)
        return getattr(user_type, "name", None)

    def get_department(self, obj):
        user_type = self._get_user_type(obj)
        department = getattr(user_type, "department", None)
        return getattr(department, "id", None)

    def get_department_name(self, obj):
        profile = self._get_profile(obj)
        user_type = getattr(profile, "user_type", None)
        department = getattr(user_type, "department", None)
        if getattr(department, "name", None):
            return department.name

        legacy_department = getattr(profile, "department", None)
        if getattr(legacy_department, "name", None):
            return legacy_department.name

        staff = getattr(profile, "staff", None)
        staff_department = getattr(staff, "department_master", None)
        return getattr(staff_department, "name", None)

    def get_role(self, obj):
        user_type = self._get_user_type(obj)
        role = getattr(user_type, "role", None)
        return getattr(role, "id", None)

    def get_role_name(self, obj):
        profile = self._get_profile(obj)
        user_type = getattr(profile, "user_type", None)
        role = getattr(user_type, "role", None)
        if getattr(role, "name", None):
            return role.name

        legacy_role = getattr(profile, "role", None)
        return getattr(legacy_role, "name", None)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "user_type",
            "user_type_name",
            "department",
            "department_name",
            "role",
            "role_name",
        )


class TokenObtainPairWithUserSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.get_username()
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = CurrentUserSerializer(self.user).data
        return data
