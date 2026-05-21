"""Serializers for WPE master tables and user creation."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import (
    BranchMaster,
    DepartmentMaster,
    LocationMaster,
    PriceBookMaster,
    ProductTypeCategory,
    ProductTypeSubtype,
    ProductionTypeMaster,
    PurchaseTypeMaster,
    RoleMaster,
    SaleTypeMaster,
    WarehouseMaster,
    WPEUserCreation,
    WPERolePermission,
    WPEUserScreenPermission,
)


UserModel = get_user_model()


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


class ProductTypeNameValidationMixin:
    default_error_messages = {
        "blank_name": "Name is required.",
    }

    def validate_name(self, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            self.fail("blank_name")
        return normalized

    def validate_description(self, value: str) -> str:
        return (value or "").strip()

    def _validate_exact_name_uniqueness(
        self,
        *,
        model_cls,
        name: str,
        instance=None,
        filters: dict[str, object] | None = None,
    ) -> None:
        queryset = model_cls.objects.filter(name=name, **(filters or {}))
        if instance and instance.pk:
            queryset = queryset.exclude(pk=instance.pk)
        if queryset.exists():
            raise serializers.ValidationError({"name": "A record with this exact name already exists."})


class ProductTypeSubtypeNestedSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = ProductTypeSubtype
        fields = (
            "id",
            "unique_id",
            "category",
            "category_name",
            "name",
            "code",
            "description",
            "sort_order",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "code", "created_at", "updated_at")


class ProductTypeCategorySerializer(ProductTypeNameValidationMixin, serializers.ModelSerializer):
    subtype_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = ProductTypeCategory
        fields = (
            "id",
            "unique_id",
            "name",
            "code",
            "description",
            "sort_order",
            "subtype_count",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "code", "subtype_count", "created_at", "updated_at")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        name = attrs.get("name", getattr(self.instance, "name", ""))
        self._validate_exact_name_uniqueness(
            model_cls=ProductTypeCategory,
            name=name,
            instance=self.instance,
        )
        return attrs


class ProductTypeCategoryTreeSerializer(ProductTypeCategorySerializer):
    subtypes = serializers.SerializerMethodField()

    class Meta(ProductTypeCategorySerializer.Meta):
        fields = ProductTypeCategorySerializer.Meta.fields + ("subtypes",)

    def get_subtypes(self, obj):
        subtypes = getattr(obj, "prefetched_subtypes", None)
        if subtypes is None:
            subtypes = obj.subtypes.all()
        return ProductTypeSubtypeNestedSerializer(subtypes, many=True).data


class ProductTypeSubtypeSerializer(ProductTypeNameValidationMixin, serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = ProductTypeSubtype
        fields = (
            "id",
            "unique_id",
            "category",
            "category_name",
            "name",
            "code",
            "description",
            "sort_order",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "code", "category_name", "created_at", "updated_at")
        validators = []

    def validate(self, attrs):
        attrs = super().validate(attrs)
        category = attrs.get("category", getattr(self.instance, "category", None))
        name = attrs.get("name", getattr(self.instance, "name", ""))

        if category is None:
            raise serializers.ValidationError({"category": "Category is required."})

        self._validate_exact_name_uniqueness(
            model_cls=ProductTypeSubtype,
            name=name,
            instance=self.instance,
            filters={"category": category},
        )
        return attrs


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
        from django.db import transaction

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

        with transaction.atomic():
            django_user = UserModel.objects.create_user(
                username=username,
                password=password,
                email=validated_data.get("email", ""),
                first_name=validated_data.get("full_name", "").split()[0] if validated_data.get("full_name") else "",
            )
            instance = WPEUserCreation.objects.create(user=django_user, **validated_data)
            for field, items in m2m_fields.items():
                getattr(instance, field).set(items)

        return instance

    def update(self, instance, validated_data):
        from django.db import transaction

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

        with transaction.atomic():
            if instance.user_id:
                django_user = instance.user
                if username:
                    django_user.username = username
                if password:
                    django_user.set_password(password)
                if username or password:
                    django_user.save()

            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            for field, items in m2m_fields.items():
                if items is not None:
                    getattr(instance, field).set(items)

        return instance


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
