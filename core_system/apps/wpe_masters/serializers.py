"""Serializers for WPE master tables and user creation."""

from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import (
    BranchMaster,
    DepartmentMaster,
    LocationMaster,
    PriceBookMaster,
    ProductionTypeMaster,
    PurchaseTypeMaster,
    RoleMaster,
    SaleTypeMaster,
    WarehouseMaster,
    WPEUserCreation,
    WPERolePermission,
    WPEUserScreenPermission,
)
from .services import upsert_wpe_user_creation


class BaseMasterSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ("id", "unique_id", "name", "is_active", "created_at", "updated_at")
        read_only_fields = ("unique_id", "created_at", "updated_at")


class LocationMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = LocationMaster


class BranchMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = BranchMaster


class PriceBookMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = PriceBookMaster


class WarehouseMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = WarehouseMaster


class ProductionTypeMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = ProductionTypeMaster


class SaleTypeMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = SaleTypeMaster


class PurchaseTypeMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = PurchaseTypeMaster


class RoleMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = RoleMaster


class DepartmentMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = DepartmentMaster


class WPEUserCreationReadSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True, default=None)
    default_branch_name = serializers.CharField(source="default_branch.name", read_only=True, default=None)
    role_name = serializers.CharField(source="role.name", read_only=True, default=None)
    authorized_branches = BranchMasterSerializer(many=True, read_only=True)
    authorized_price_books = PriceBookMasterSerializer(many=True, read_only=True)
    authorized_warehouses = WarehouseMasterSerializer(many=True, read_only=True)
    authorized_production_types = ProductionTypeMasterSerializer(many=True, read_only=True)
    authorized_sale_types = SaleTypeMasterSerializer(many=True, read_only=True)
    authorized_purchase_types = PurchaseTypeMasterSerializer(many=True, read_only=True)

    class Meta:
        model = WPEUserCreation
        fields = (
            "id",
            "unique_id",
            "username",
            "full_name",
            "job_title",
            "email",
            "phone_no",
            "location",
            "location_name",
            "default_branch",
            "default_branch_name",
            "authorized_branches",
            "authorized_price_books",
            "authorized_warehouses",
            "authorized_production_types",
            "authorized_sale_types",
            "authorized_purchase_types",
            "role",
            "role_name",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")


class WPEUserCreationWriteSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    confirm_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    authorized_branches = serializers.PrimaryKeyRelatedField(
        queryset=BranchMaster.objects.filter(is_active=True), many=True, required=False
    )
    authorized_price_books = serializers.PrimaryKeyRelatedField(
        queryset=PriceBookMaster.objects.filter(is_active=True), many=True, required=False
    )
    authorized_warehouses = serializers.PrimaryKeyRelatedField(
        queryset=WarehouseMaster.objects.filter(is_active=True), many=True, required=False
    )
    authorized_production_types = serializers.PrimaryKeyRelatedField(
        queryset=ProductionTypeMaster.objects.filter(is_active=True), many=True, required=False
    )
    authorized_sale_types = serializers.PrimaryKeyRelatedField(
        queryset=SaleTypeMaster.objects.filter(is_active=True), many=True, required=False
    )
    authorized_purchase_types = serializers.PrimaryKeyRelatedField(
        queryset=PurchaseTypeMaster.objects.filter(is_active=True), many=True, required=False
    )

    class Meta:
        model = WPEUserCreation
        fields = (
            "id",
            "unique_id",
            "username",
            "password",
            "confirm_password",
            "full_name",
            "job_title",
            "email",
            "phone_no",
            "location",
            "default_branch",
            "authorized_branches",
            "authorized_price_books",
            "authorized_warehouses",
            "authorized_production_types",
            "authorized_sale_types",
            "authorized_purchase_types",
            "role",
            "is_active",
        )
        read_only_fields = ("unique_id",)

    def validate(self, attrs):
        password = attrs.get("password", "")
        confirm_password = attrs.pop("confirm_password", "")
        instance = self.instance

        if not instance and not password:
            raise serializers.ValidationError({"password": "Password is required when creating a new user."})

        if password:
            if password != confirm_password:
                raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
            validate_password(password)

        return attrs

    def create(self, validated_data):
        username = validated_data.pop("username")
        password = validated_data.pop("password", None)
        m2m_fields = {
            "authorized_branches": validated_data.pop("authorized_branches", []),
            "authorized_price_books": validated_data.pop("authorized_price_books", []),
            "authorized_warehouses": validated_data.pop("authorized_warehouses", []),
            "authorized_production_types": validated_data.pop("authorized_production_types", []),
            "authorized_sale_types": validated_data.pop("authorized_sale_types", []),
            "authorized_purchase_types": validated_data.pop("authorized_purchase_types", []),
        }
        return upsert_wpe_user_creation(
            username=username,
            password=password,
            full_name=validated_data.get("full_name", ""),
            job_title=validated_data.get("job_title"),
            email=validated_data.get("email"),
            phone_no=validated_data.get("phone_no"),
            location=validated_data.get("location"),
            default_branch=validated_data.get("default_branch"),
            role=validated_data.get("role"),
            is_active=validated_data.get("is_active", True),
            authorized_branches=m2m_fields["authorized_branches"],
            authorized_price_books=m2m_fields["authorized_price_books"],
            authorized_warehouses=m2m_fields["authorized_warehouses"],
            authorized_production_types=m2m_fields["authorized_production_types"],
            authorized_sale_types=m2m_fields["authorized_sale_types"],
            authorized_purchase_types=m2m_fields["authorized_purchase_types"],
        )

    def update(self, instance, validated_data):
        username = validated_data.pop("username", None)
        password = validated_data.pop("password", None)
        m2m_fields = {
            "authorized_branches": validated_data.pop("authorized_branches", None),
            "authorized_price_books": validated_data.pop("authorized_price_books", None),
            "authorized_warehouses": validated_data.pop("authorized_warehouses", None),
            "authorized_production_types": validated_data.pop("authorized_production_types", None),
            "authorized_sale_types": validated_data.pop("authorized_sale_types", None),
            "authorized_purchase_types": validated_data.pop("authorized_purchase_types", None),
        }
        return upsert_wpe_user_creation(
            instance=instance,
            username=username or instance.user.username,
            password=password,
            full_name=validated_data.get("full_name", instance.full_name),
            job_title=validated_data.get("job_title", instance.job_title),
            email=validated_data.get("email", instance.email),
            phone_no=validated_data.get("phone_no", instance.phone_no),
            location=validated_data.get("location", instance.location),
            default_branch=validated_data.get("default_branch", instance.default_branch),
            role=validated_data.get("role", instance.role),
            is_active=validated_data.get("is_active", instance.is_active),
            authorized_branches=m2m_fields["authorized_branches"],
            authorized_price_books=m2m_fields["authorized_price_books"],
            authorized_warehouses=m2m_fields["authorized_warehouses"],
            authorized_production_types=m2m_fields["authorized_production_types"],
            authorized_sale_types=m2m_fields["authorized_sale_types"],
            authorized_purchase_types=m2m_fields["authorized_purchase_types"],
        )


PERMISSION_FIELDS = (
    "view_all", "view_self", "can_add", "can_edit",
    "can_duplicate", "can_delete",
    "generate_invoice_access", "invoice_access", "access",
)


class WPERolePermissionSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    main_screen_name = serializers.CharField(source="main_screen.name", read_only=True)

    class Meta:
        model = WPERolePermission
        fields = (
            "id", "role", "role_name", "main_screen", "main_screen_name",
        ) + PERMISSION_FIELDS + ("created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")


class WPEUserScreenPermissionSerializer(serializers.ModelSerializer):
    screen_name = serializers.CharField(source="user_screen.screen_name", read_only=True)
    screen_section_name = serializers.CharField(source="user_screen.screen_section.name", read_only=True)

    class Meta:
        model = WPEUserScreenPermission
        fields = (
            "id", "user_screen", "screen_name", "screen_section_name",
        ) + PERMISSION_FIELDS + ("created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")
