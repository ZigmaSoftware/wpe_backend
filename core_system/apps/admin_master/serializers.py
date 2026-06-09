"""Serializers for admin master masters, user provisioning, and RBAC."""

from __future__ import annotations

from rest_framework import serializers

from apps.login_home.models import Department
from apps.wpe_masters.models import DepartmentMaster, DesignationMaster, RoleMaster

from .models import (
    SCREEN_ACTIONS, 
    MainScreen,
    ScreenSection,
    Staff,
    UserCreation,
    UserScreen,
    UserType,
    UserTypePermission,
)
from .services import upsert_permission_assignments, upsert_user_creation
from .validators import (
    normalize_action_permissions,
    normalize_screen_actions,
    validate_mobile_number,
    validate_scope_relationship,
)

class MainScreenSerializer(serializers.ModelSerializer):
    screen_name = serializers.CharField(source="name")
    is_active = serializers.BooleanField(source="status", required=False)

    class Meta:
        model = MainScreen
        fields = ("id", "unique_id", "screen_name", "code", "order_no", "is_active")
        read_only_fields = ("unique_id",)
        extra_kwargs = {
            "code": {"required": False, "allow_blank": True, "allow_null": True},
        }


class ScreenSectionSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source="name")
    main_screen_name = serializers.CharField(source="main_screen.name", read_only=True)

    class Meta:
        model = ScreenSection
        fields = (
            "id",
            "unique_id",
            "main_screen",
            "main_screen_name",
            "section_name",
            "code",
            "order_no",
            "is_active",
            "description",
        )
        read_only_fields = ("unique_id", "main_screen_name")
        extra_kwargs = {
            "code": {"required": False, "allow_blank": True, "allow_null": True},
        }


class UserScreenSerializer(serializers.ModelSerializer):
    main_screen_name = serializers.CharField(source="main_screen.name", read_only=True)
    screen_section_name = serializers.CharField(source="screen_section.name", read_only=True)
    route_path = serializers.CharField(
        source="folder_name",
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    class Meta:
        model = UserScreen
        fields = (
            "id",
            "unique_id",
            "main_screen",
            "main_screen_name",
            "screen_section",
            "screen_section_name",
            "screen_name",
            "code",
            "route_path",
            "order_no",
            "icon",
            "description",
            "is_active",
            "available_actions",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")
        extra_kwargs = {
            "code": {"required": False, "allow_blank": True, "allow_null": True},
        }

    def validate_available_actions(self, value):
        return normalize_screen_actions(value)

    def validate(self, attrs):
        main_screen = attrs.get("main_screen") or getattr(self.instance, "main_screen", None)
        screen_section = attrs.get("screen_section") or getattr(self.instance, "screen_section", None)
        validate_scope_relationship(main_screen=main_screen, screen_section=screen_section)
        return attrs


class UserTypeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    department = serializers.PrimaryKeyRelatedField(queryset=DepartmentMaster.objects.all())
    role = serializers.PrimaryKeyRelatedField(queryset=RoleMaster.objects.all())

    class Meta:
        model = UserType
        fields = (
            "id",
            "unique_id",
            "department",
            "department_name",
            "role",
            "role_name",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")

    def validate(self, attrs):
        department = attrs.get("department") or getattr(self.instance, "department", None)
        role = attrs.get("role") or getattr(self.instance, "role", None)

        if not department:
            raise serializers.ValidationError({"department": "Department is required."})
        if not role:
            raise serializers.ValidationError({"role": "Role is required."})

        queryset = UserType.objects.filter(department=department, role=role)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                {"role": "A user type for this department and role already exists."}
            )

        return attrs


class StaffSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    staff_code = serializers.CharField(max_length=50, required=True)
    name = serializers.CharField(max_length=150, required=True)
    age = serializers.IntegerField(min_value=1, required=True)
    department = serializers.IntegerField(source="department_master_id", read_only=True)
    department_name = serializers.CharField(source="department_master.name", read_only=True, allow_null=True)
    designation_name = serializers.CharField(source="designation_master.name", read_only=True, allow_null=True)
    role = serializers.IntegerField(source="role_master_id", read_only=True)
    role_name = serializers.CharField(source="role_master.name", read_only=True, allow_null=True)
    designation = serializers.PrimaryKeyRelatedField(
        source="designation_master",
        queryset=DesignationMaster.objects.filter(is_active=True),
        required=True,
    )
    mobile = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    emergency_contact_no = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    joining_date = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=Staff.Gender.choices,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    class Meta:
        model = Staff
        fields = (
            "id",
            "unique_id",
            "staff_code",
            "name",
            "age",
            "department",
            "department_name",
            "designation",
            "designation_name",
            "role",
            "role_name",
            "mobile",
            "email",
            "joining_date",
            "gender",
            "address",
            "emergency_contact_no",
            "photo",
            "photo_url",
            "is_active",
            "remarks",
        )
        read_only_fields = ("id", "unique_id", "photo_url")

    def get_photo_url(self, obj):
        if not obj.photo:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.photo.url)
        return obj.photo.url

    def validate_staff_code(self, value):
        normalized = (value or "").strip()
        if not normalized:
            raise serializers.ValidationError("Employee ID is required.")
        return normalized

    def validate_name(self, value):
        normalized = (value or "").strip()
        if not normalized:
            raise serializers.ValidationError("Name is required.")
        return normalized

    def validate_mobile(self, value):
        normalized = validate_mobile_number(value)
        if not normalized:
            raise serializers.ValidationError("Phone no is required.")
        return normalized

    def validate_emergency_contact_no(self, value):
        return validate_mobile_number(value)

    def validate(self, attrs):
        designation_master = attrs.get("designation_master") or getattr(self.instance, "designation_master", None)

        if not designation_master:
            raise serializers.ValidationError({"designation": "Desigination is required."})

        attrs["department_master"] = designation_master.department
        attrs["role_master"] = (
            RoleMaster.objects.filter(
                designation_id=designation_master.id,
                is_active=True,
            )
            .order_by("id")
            .first()
        )

        if attrs.get("joining_date") == "":
            attrs["joining_date"] = None
        if attrs.get("gender") == "":
            attrs["gender"] = None
        if attrs.get("emergency_contact_no") == "":
            attrs["emergency_contact_no"] = None
        if attrs.get("photo") == "":
            attrs["photo"] = None
        attrs["department"] = _resolve_legacy_department(designation_master.department)
        attrs["designation"] = designation_master.name
        return attrs


def _resolve_legacy_department(department_master: DepartmentMaster | None) -> Department | None:
    if not department_master or not department_master.name:
        return None
    return Department.objects.filter(name__iexact=department_master.name.strip()).order_by("id").first()

class UserCreationReadSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    staff_id = serializers.CharField(source="staff.staff_code", read_only=True)
    full_name = serializers.CharField(source="staff.name", read_only=True)
    user_type = serializers.IntegerField(source="user_type_id", read_only=True)
    user_type_name = serializers.CharField(source="user_type.name", read_only=True)
    mobile_no = serializers.CharField(source="staff.mobile", read_only=True)
    email = serializers.SerializerMethodField()
    company_name = serializers.CharField(source="company.name", read_only=True)
    department = serializers.IntegerField(source="user_type.department_id", read_only=True)
    department_name = serializers.SerializerMethodField()
    role = serializers.IntegerField(source="user_type.role_id", read_only=True)
    role_name = serializers.SerializerMethodField()
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)

    class Meta:
        model = UserCreation
        fields = (
            "id",
            "unique_id",
            "user",
            "username",
            "staff",
            "staff_id",
            "full_name",
            "user_type",
            "user_type_name",
            "mobile_no",
            "email",
            "department",
            "department_name",
            "role",
            "role_name",
            "company",
            "company_name",
            "account_status",
            "is_active",
            "last_login",
            "password_changed_at",
            "failed_login_attempts",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_email(self, obj):
        if obj.user_id and obj.user.email:
            return obj.user.email
        if obj.staff_id and obj.staff.email:
            return obj.staff.email
        return ""

    def get_department_name(self, obj):
        user_type = getattr(obj, "user_type", None)
        department = getattr(user_type, "department", None)
        return getattr(department, "name", "")

    def get_role_name(self, obj):
        user_type = getattr(obj, "user_type", None)
        role = getattr(user_type, "role", None)
        return getattr(role, "name", "")


class UserCreationWriteSerializer(serializers.Serializer):
    staff = serializers.PrimaryKeyRelatedField(queryset=Staff.objects.all())
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    confirm_password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    user_type = serializers.PrimaryKeyRelatedField(queryset=UserType.objects.select_related("department", "role").filter(is_active=True))
    mobile_no = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    company = serializers.PrimaryKeyRelatedField(
        queryset=UserCreation._meta.get_field("company").remote_field.model.objects.all(),
        required=True,
    )
    account_status = serializers.ChoiceField(
        choices=UserCreation.AccountStatus.choices,
        required=False,
        default=UserCreation.AccountStatus.ACTIVE,
    )

    def validate_mobile_no(self, value):
        return validate_mobile_number(value)

    def validate(self, attrs):
        resolved_user_type = attrs.get("user_type")
        password = attrs.get("password")
        confirm_password = attrs.pop("confirm_password", None)

        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "Password is required."})

        if password and not confirm_password:
            raise serializers.ValidationError({"confirm_password": "Confirm password is required."})

        if password and confirm_password != password:
            raise serializers.ValidationError({"confirm_password": "Confirm password does not match."})

        if confirm_password and not password:
            raise serializers.ValidationError({"password": "Password is required when confirm password is supplied."})

        if not resolved_user_type:
            raise serializers.ValidationError({"user_type": "User type is required."})

        department = getattr(resolved_user_type, "department", None)
        role = getattr(resolved_user_type, "role", None)

        if not department:
            raise serializers.ValidationError({"user_type": "The selected user type is missing a department mapping."})
        if not role:
            raise serializers.ValidationError({"user_type": "The selected user type is missing a role mapping."})

        attrs["department"] = _resolve_legacy_department(department)
        attrs["role"] = _resolve_legacy_role(role)
        return attrs

    def create(self, validated_data):
        return upsert_user_creation(**validated_data)

    def update(self, instance, validated_data):
        return upsert_user_creation(instance=instance, **validated_data)


class UserTypePermissionSummarySerializer(serializers.ModelSerializer):
    user_type = serializers.IntegerField(source="id", read_only=True)
    user_type_name = serializers.CharField(source="name", read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = UserType
        fields = ("id", "user_type", "user_type_name", "is_active")
        read_only_fields = fields

    def get_is_active(self, obj):
        active_permission_count = getattr(obj, "active_permission_count", None)
        if active_permission_count is not None:
            return active_permission_count > 0
        return obj.permissions.filter(status=True).exists()


class UserTypePermissionSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(source="status", required=False)
    user_type_name = serializers.CharField(source="user_type.name", read_only=True)
    main_screen_name = serializers.CharField(source="main_screen.name", read_only=True)
    screen_section_name = serializers.CharField(source="screen_section.name", read_only=True)
    user_screen_name = serializers.CharField(source="user_screen.screen_name", read_only=True)

    class Meta:
        model = UserTypePermission
        fields = (
            "id",
            "unique_id",
            "user_type",
            "user_type_name",
            "scope_type",
            "main_screen",
            "main_screen_name",
            "screen_section",
            "screen_section_name",
            "user_screen",
            "user_screen_name",
            "action_permissions",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")

    def validate(self, attrs):
        scope_type = attrs.get("scope_type") or getattr(self.instance, "scope_type", None)
        main_screen = attrs.get("main_screen") or getattr(self.instance, "main_screen", None)
        screen_section = attrs.get("screen_section") or getattr(self.instance, "screen_section", None)
        user_screen = attrs.get("user_screen") or getattr(self.instance, "user_screen", None)
        user_type = attrs.get("user_type") or getattr(self.instance, "user_type", None)

        if scope_type == UserTypePermission.ScopeType.SECTION and screen_section and not main_screen:
            attrs["main_screen"] = screen_section.main_screen
            main_screen = attrs["main_screen"]

        if scope_type == UserTypePermission.ScopeType.SCREEN and user_screen:
            attrs["main_screen"] = user_screen.main_screen
            attrs["screen_section"] = user_screen.screen_section
            main_screen = attrs["main_screen"]
            screen_section = attrs["screen_section"]

        validate_scope_relationship(
            main_screen=main_screen,
            screen_section=screen_section,
            user_screen=user_screen,
        )

        available_actions = user_screen.available_actions if user_screen else SCREEN_ACTIONS
        attrs["action_permissions"] = normalize_action_permissions(
            attrs.get("action_permissions", getattr(self.instance, "action_permissions", None)),
            available_actions=available_actions,
        )

        if not main_screen:
            raise serializers.ValidationError({"main_screen": "Main screen is required."})
        if not user_type:
            raise serializers.ValidationError({"user_type": "User type is required."})

        return attrs

    def create(self, validated_data):
        permissions = upsert_permission_assignments(
            user_type=validated_data["user_type"],
            permission_entries=[validated_data],
        )
        return permissions[0]

    def update(self, instance, validated_data):
        merged_data = {
            "scope_type": validated_data.get("scope_type", instance.scope_type),
            "main_screen": validated_data.get("main_screen", instance.main_screen),
            "screen_section": validated_data.get("screen_section", instance.screen_section),
            "user_screen": validated_data.get("user_screen", instance.user_screen),
            "action_permissions": validated_data.get("action_permissions", instance.action_permissions),
            "is_active": validated_data.get("status", instance.status),
        }
        permissions = upsert_permission_assignments(
            user_type=validated_data.get("user_type", instance.user_type),
            permission_entries=[merged_data],
        )
        return permissions[0]


class PermissionAssignmentEntrySerializer(serializers.Serializer):
    scope_type = serializers.ChoiceField(choices=UserTypePermission.ScopeType.choices)
    main_screen = serializers.PrimaryKeyRelatedField(
        queryset=MainScreen.objects.all(),
        required=False,
        allow_null=True,
    )
    screen_section = serializers.PrimaryKeyRelatedField(
        queryset=ScreenSection.objects.all(),
        required=False,
        allow_null=True,
    )
    user_screen = serializers.PrimaryKeyRelatedField(
        queryset=UserScreen.objects.all(),
        required=False,
        allow_null=True,
    )
    action_permissions = serializers.JSONField(required=False)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        scope_type = attrs["scope_type"]
        main_screen = attrs.get("main_screen")
        screen_section = attrs.get("screen_section")
        user_screen = attrs.get("user_screen")

        if scope_type == UserTypePermission.ScopeType.SECTION and screen_section and not main_screen:
            attrs["main_screen"] = screen_section.main_screen
            main_screen = attrs["main_screen"]

        if scope_type == UserTypePermission.ScopeType.SCREEN and user_screen:
            attrs["main_screen"] = user_screen.main_screen
            attrs["screen_section"] = user_screen.screen_section
            main_screen = attrs["main_screen"]
            screen_section = attrs["screen_section"]

        validate_scope_relationship(
            main_screen=main_screen,
            screen_section=screen_section,
            user_screen=user_screen,
        )

        available_actions = user_screen.available_actions if user_screen else SCREEN_ACTIONS
        attrs["action_permissions"] = normalize_action_permissions(
            attrs.get("action_permissions"),
            available_actions=available_actions,
        )
        return attrs


class PermissionAssignmentSerializer(serializers.Serializer):
    user_type = serializers.PrimaryKeyRelatedField(queryset=UserType.objects.all())
    permissions = PermissionAssignmentEntrySerializer(many=True)

    def create(self, validated_data):
        return upsert_permission_assignments(
            user_type=validated_data["user_type"],
            permission_entries=validated_data["permissions"],
        )
