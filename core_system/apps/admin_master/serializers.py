"""Serializers for admin master masters, user provisioning, and RBAC."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.login_home.models import Department

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


UserModel = get_user_model()


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


class StaffSerializer(serializers.ModelSerializer):
    staff_id = serializers.CharField(source="staff_code", read_only=True)
    staff_name = serializers.CharField(source="name")
    mobile_no = serializers.CharField(
        source="mobile",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    department_name = serializers.CharField(source="department.name", read_only=True)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Staff
        fields = (
            "id",
            "unique_id",
            "staff_id",
            "staff_name",
            "mobile_no",
            "email",
            "department",
            "department_name",
            "designation",
            "is_active",
        )
        read_only_fields = ("unique_id", "staff_id", "department_name")

    def validate_mobile_no(self, value):
        return validate_mobile_number(value)


class UserTypeSerializer(serializers.ModelSerializer):
    user_type = serializers.CharField(source="name")

    class Meta:
        model = UserType
        fields = (
            "id",
            "unique_id",
            "user_type",
            "code",
            "is_active",
            "under_users",
            "company_wise",
            "project_wise",
            "department_wise",
            "user_wise",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")
        extra_kwargs = {
            "code": {"required": False, "allow_blank": True, "allow_null": True},
        }


class UserCreationReadSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    staff_id = serializers.CharField(source="staff.staff_code", read_only=True)
    staff_name = serializers.CharField(source="staff.name", read_only=True)
    mobile_no = serializers.CharField(source="staff.mobile", read_only=True)
    email = serializers.SerializerMethodField()
    user_type_name = serializers.CharField(source="user_type.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    team_members = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = UserCreation
        fields = (
            "id",
            "unique_id",
            "user",
            "username",
            "staff",
            "staff_id",
            "staff_name",
            "mobile_no",
            "email",
            "user_type",
            "user_type_name",
            "company",
            "company_name",
            "department",
            "department_name",
            "project",
            "under_users",
            "account_status",
            "is_active",
            "last_login",
            "password_changed_at",
            "failed_login_attempts",
            "force_password_change",
            "is_team_head",
            "team_members",
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


class UserCreationWriteSerializer(serializers.Serializer):
    staff = serializers.PrimaryKeyRelatedField(queryset=Staff.objects.all())
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    confirm_password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    user_type = serializers.PrimaryKeyRelatedField(queryset=UserType.objects.all())
    mobile_no = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    first_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    company = serializers.PrimaryKeyRelatedField(
        queryset=UserCreation._meta.get_field("company").remote_field.model.objects.all(),
        required=False,
        allow_null=True,
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=False,
        allow_null=True,
    )
    project = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    under_users = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    account_status = serializers.ChoiceField(
        choices=UserCreation.AccountStatus.choices,
        required=False,
        default=UserCreation.AccountStatus.ACTIVE,
    )
    force_password_change = serializers.BooleanField(required=False, default=False)
    is_team_head = serializers.BooleanField(required=False, default=False)
    team_members = serializers.PrimaryKeyRelatedField(
        queryset=UserCreation.objects.all(),
        many=True,
        required=False,
    )
    designation = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_mobile_no(self, value):
        return validate_mobile_number(value)

    def validate(self, attrs):
        password = attrs.get("password")
        confirm_password = attrs.pop("confirm_password", None)

        if password and confirm_password != password:
            raise serializers.ValidationError({"confirm_password": "Confirm password does not match."})

        if confirm_password and not password:
            raise serializers.ValidationError({"password": "Password is required when confirm password is supplied."})

        if password:
            user = UserModel(
                username=attrs.get("username", getattr(getattr(self.instance, "user", None), "username", "")),
                email=attrs.get("email") or "",
            )
            validate_password(password, user=user)

        return attrs

    def create(self, validated_data):
        team_members = validated_data.pop("team_members", [])
        return upsert_user_creation(team_members=team_members, **validated_data)

    def update(self, instance, validated_data):
        team_members = validated_data.pop("team_members", None)
        return upsert_user_creation(instance=instance, team_members=team_members, **validated_data)


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
