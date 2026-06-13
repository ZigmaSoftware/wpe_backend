"""Serializers for WPE master tables and user creation."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import (
    BranchMaster,
    DepartmentMaster,
    DesignationMaster,
    ItemMaster,
    LocationMaster,
    PrinterMaster,
    PriceBookMaster,
    ProductTypeCategory,
    ProductTypeSubtype,
    ProductionTypeMaster,
    PurchaseTypeMaster,
    QRLabelTemplateMaster,
    RoleMaster,
    SaleTypeMaster,
    SerialPortConfigurationMaster,
    StoreMaster,
    UnitMaster,
    WarehouseMaster,
    WeighmentScaleMaster,
    WPEUserCreation,
)
from apps.production.models import ProductionMachine


UserModel = get_user_model()


class BaseMasterSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ("id", "unique_id", "name", "is_active", "created_at", "updated_at")
        read_only_fields = ("unique_id", "created_at", "updated_at")


class CodeTrackedMasterSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ("id", "unique_id", "code", "name", "description", "is_active", "created_at", "updated_at")
        read_only_fields = ("unique_id", "code", "created_at", "updated_at")


class LocationMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = LocationMaster
        fields = BaseMasterSerializer.Meta.fields + ("center_type",)


class BranchMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = BranchMaster


class PriceBookMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = PriceBookMaster


class WarehouseMasterSerializer(CodeTrackedMasterSerializer):
    class Meta(CodeTrackedMasterSerializer.Meta):
        model = WarehouseMaster
        fields = CodeTrackedMasterSerializer.Meta.fields + ("warehouse_type",)


class ProductionTypeMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = ProductionTypeMaster


class SaleTypeMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = SaleTypeMaster


class PurchaseTypeMasterSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = PurchaseTypeMaster


class StoreMasterSerializer(CodeTrackedMasterSerializer):
    class Meta(CodeTrackedMasterSerializer.Meta):
        model = StoreMaster


class DepartmentMasterSerializer(CodeTrackedMasterSerializer):
    department_head_name = serializers.CharField(source="department_head.full_name", read_only=True, allow_null=True)
    department_head = serializers.PrimaryKeyRelatedField(
        queryset=WPEUserCreation.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta(CodeTrackedMasterSerializer.Meta):
        model = DepartmentMaster
        fields = CodeTrackedMasterSerializer.Meta.fields + ("department_head", "department_head_name")


class DesignationMasterSerializer(CodeTrackedMasterSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    department = serializers.PrimaryKeyRelatedField(queryset=DepartmentMaster.objects.filter(is_active=True))

    class Meta(CodeTrackedMasterSerializer.Meta):
        model = DesignationMaster
        fields = CodeTrackedMasterSerializer.Meta.fields + ("department", "department_name")


class RoleMasterSerializer(CodeTrackedMasterSerializer):
    designation_name = serializers.CharField(source="designation.name", read_only=True, allow_null=True)
    designation = serializers.PrimaryKeyRelatedField(
        queryset=DesignationMaster.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta(CodeTrackedMasterSerializer.Meta):
        model = RoleMaster
        fields = CodeTrackedMasterSerializer.Meta.fields + ("designation", "designation_name")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        designation = attrs.get("designation", getattr(self.instance, "designation", None))
        if designation is None:
            raise serializers.ValidationError({"designation": "Designation is required."})
        return attrs


class UnitMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitMaster
        fields = (
            "id",
            "unique_id",
            "uom_code",
            "name",
            "decimal_allowed",
            "decimal_places",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "created_at", "updated_at")

    def validate_uom_code(self, value: str) -> str:
        normalized = (value or "").strip().upper()
        if not normalized:
            raise serializers.ValidationError("UOM code is required.")
        queryset = UnitMaster.objects.filter(uom_code__iexact=normalized)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A unit with this UOM code already exists.")
        return normalized

    def validate_name(self, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise serializers.ValidationError("UOM name is required.")
        return normalized

    def validate(self, attrs):
        attrs = super().validate(attrs)
        decimal_allowed = attrs.get("decimal_allowed", getattr(self.instance, "decimal_allowed", False))
        decimal_places = attrs.get("decimal_places", getattr(self.instance, "decimal_places", 0))
        if not decimal_allowed:
            attrs["decimal_places"] = 0
        elif decimal_places < 0:
            raise serializers.ValidationError({"decimal_places": "Decimal places must be zero or greater."})
        return attrs


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
    variant_count = serializers.IntegerField(read_only=True, default=0)

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
            "variant_count",
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
    variant_count = serializers.IntegerField(read_only=True, default=0)

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
            "variant_count",
            "sort_order",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("unique_id", "code", "category_name", "variant_count", "created_at", "updated_at")
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


class ItemMasterSerializer(serializers.ModelSerializer):
    sub_category_name = serializers.CharField(source="sub_category.name", read_only=True)
    category = serializers.IntegerField(source="sub_category.category_id", read_only=True)
    category_name = serializers.CharField(source="sub_category.category.name", read_only=True)
    uom_code = serializers.CharField(source="uom.uom_code", read_only=True)
    uom_name = serializers.CharField(source="uom.name", read_only=True)
    sub_category = serializers.PrimaryKeyRelatedField(queryset=ProductTypeSubtype.objects.filter(is_active=True, category__is_active=True))
    uom = serializers.PrimaryKeyRelatedField(queryset=UnitMaster.objects.filter(is_active=True))

    class Meta:
        model = ItemMaster
        fields = (
            "id",
            "unique_id",
            "item_code",
            "item_name",
            "sub_category",
            "sub_category_name",
            "category",
            "category_name",
            "description",
            "item_type",
            "uom",
            "uom_code",
            "uom_name",
            "hsn_code",
            "gst_percentage",
            "minimum_stock",
            "maximum_stock",
            "reorder_level",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "unique_id",
            "item_code",
            "sub_category_name",
            "category",
            "category_name",
            "uom_code",
            "uom_name",
            "created_at",
            "updated_at",
        )

    def validate_item_name(self, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise serializers.ValidationError("Item name is required.")
        return normalized

    def validate_hsn_code(self, value: str) -> str:
        return (value or "").strip()

    def validate_description(self, value: str) -> str:
        return (value or "").strip()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        minimum_stock = attrs.get("minimum_stock", getattr(self.instance, "minimum_stock", None))
        maximum_stock = attrs.get("maximum_stock", getattr(self.instance, "maximum_stock", None))
        reorder_level = attrs.get("reorder_level", getattr(self.instance, "reorder_level", None))
        sub_category = attrs.get("sub_category", getattr(self.instance, "sub_category", None))
        item_name = attrs.get("item_name", getattr(self.instance, "item_name", ""))
        if sub_category is None:
            raise serializers.ValidationError({"sub_category": "Item sub category is required."})
        duplicate_queryset = ItemMaster.objects.filter(sub_category=sub_category, item_name=item_name)
        if self.instance and self.instance.pk:
            duplicate_queryset = duplicate_queryset.exclude(pk=self.instance.pk)
        if duplicate_queryset.exists():
            raise serializers.ValidationError(
                {"item_name": "An item variant with this name already exists in the selected item sub category."}
            )
        if minimum_stock is not None and maximum_stock is not None and minimum_stock > maximum_stock:
            raise serializers.ValidationError({"minimum_stock": "Minimum stock cannot exceed maximum stock."})
        if reorder_level is not None and maximum_stock is not None and reorder_level > maximum_stock:
            raise serializers.ValidationError({"reorder_level": "Reorder level cannot exceed maximum stock."})
        return attrs


class DeviceLabelCodeMasterSerializer(CodeTrackedMasterSerializer):
    def validate_name(self, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise serializers.ValidationError("Name is required.")
        return normalized

    def validate_description(self, value: str) -> str:
        return (value or "").strip()


class WeighmentScaleMasterSerializer(DeviceLabelCodeMasterSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    machine_name = serializers.CharField(source="machine.name", read_only=True)
    machine_code = serializers.CharField(source="machine.machine_code", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True, allow_null=True)
    unit_code = serializers.CharField(source="unit.uom_code", read_only=True, allow_null=True)
    department = serializers.PrimaryKeyRelatedField(queryset=DepartmentMaster.objects.filter(is_active=True))
    machine = serializers.PrimaryKeyRelatedField(queryset=ProductionMachine.objects.filter(is_active=True))
    unit = serializers.PrimaryKeyRelatedField(
        queryset=UnitMaster.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta(CodeTrackedMasterSerializer.Meta):
        model = WeighmentScaleMaster
        fields = CodeTrackedMasterSerializer.Meta.fields + (
            "department",
            "department_name",
            "machine",
            "machine_name",
            "machine_code",
            "connection_type",
            "port_name",
            "baud_rate",
            "data_bits",
            "parity",
            "stop_bits",
            "unit",
            "unit_name",
            "unit_code",
            "is_auto_capture",
        )


class PrinterMasterSerializer(DeviceLabelCodeMasterSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    department = serializers.PrimaryKeyRelatedField(queryset=DepartmentMaster.objects.filter(is_active=True))

    class Meta(CodeTrackedMasterSerializer.Meta):
        model = PrinterMaster
        fields = CodeTrackedMasterSerializer.Meta.fields + (
            "printer_type",
            "department",
            "department_name",
            "connection_type",
            "ip_address",
            "port",
            "paper_size",
        )

    def validate_paper_size(self, value: str) -> str:
        normalized = (value or "").strip()
        return normalized or "LABEL"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        connection_type = attrs.get("connection_type", getattr(self.instance, "connection_type", None))
        ip_address = attrs.get("ip_address", getattr(self.instance, "ip_address", None))
        port = attrs.get("port", getattr(self.instance, "port", None))

        if connection_type == PrinterMaster.ConnectionType.NETWORK:
            errors: dict[str, str] = {}
            if not ip_address:
                errors["ip_address"] = "IP address is required for network printers."
            if port in (None, ""):
                errors["port"] = "Port is required for network printers."
            if errors:
                raise serializers.ValidationError(errors)
        elif connection_type == PrinterMaster.ConnectionType.USB:
            attrs["ip_address"] = None
            attrs["port"] = None
        return attrs


class QRLabelTemplateMasterSerializer(DeviceLabelCodeMasterSerializer):
    printer_name = serializers.CharField(source="printer.name", read_only=True)
    printer_code = serializers.CharField(source="printer.code", read_only=True)
    printer = serializers.PrimaryKeyRelatedField(queryset=PrinterMaster.objects.filter(is_active=True))

    class Meta(CodeTrackedMasterSerializer.Meta):
        model = QRLabelTemplateMaster
        fields = CodeTrackedMasterSerializer.Meta.fields + (
            "label_type",
            "width",
            "height",
            "qr_data_format",
            "printer",
            "printer_name",
            "printer_code",
        )


class SerialPortConfigurationMasterSerializer(DeviceLabelCodeMasterSerializer):
    class Meta(CodeTrackedMasterSerializer.Meta):
        model = SerialPortConfigurationMaster
        fields = CodeTrackedMasterSerializer.Meta.fields + (
            "port_name",
            "baud_rate",
            "parity",
            "data_bits",
            "stop_bits",
            "timeout",
            "read_format",
        )


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
