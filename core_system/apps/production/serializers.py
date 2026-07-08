from decimal import Decimal

from django.db.models import Q
from rest_framework import serializers
from django.utils import timezone
from apps.inventory.models import ProductionInventoryTransaction
from apps.wpe_masters.models import ProductionTypeMaster
from .models import (
    BOMVariant,
    BOMVariantComponent,
    BatchWeightEntry,
    ProductionOrder,
    MaterialMovement,
    ProductionTransaction,
    ProductionSummary,
    ProductionBatch,
    ProductionOutputCapture,
    ProductionOrderMaterialPlan,
    RegrindMaterialEntry,
    BagCreationMaster,
    BinCreationMaster,
    BOMCreationMaster,
    BOMItemCreationMaster,
    ColorCreationMaster,
    PackingMaterialMaster,
    PackingTypeMaster,
    ProductionLineMaster,
    ProductionLineConnection,
    ProfileCreationMaster,
    ProfileSizeMaster,
    ProductionMachine,
    WorkCentreCreationMaster,
    get_connected_lineage_batches,
    resolve_workflow_batch_no,
)
from .services import (
    get_active_line_connection_for_machine,
    get_active_line_connection_for_order,
    resolve_inventory_baglot,
    resolve_production_machine,
)


class MaterialMovementSerializer(serializers.ModelSerializer):
    """Serializer for Material Movement"""

    class Meta:
        model = MaterialMovement
        fields = [
            "id",
            "movement_type",
            "item_id",
            "item_name",
            "item_code",
            "source_location",
            "destination_location",
            "quantity",
            "unit",
            "warehouse",
            "bin_number",
            "status",
            "movement_date",
        ]
        read_only_fields = ["id"]


class ProductionTransactionSerializer(serializers.ModelSerializer):
    """Serializer for Production Transaction"""

    class Meta:
        model = ProductionTransaction
        fields = [
            "id",
            "transaction_id",
            "transaction_type",
            "transaction_date",
            "transaction_time",
            "item_id",
            "item_number",
            "item_name",
            "item_code",
            "quantity_in",
            "quantity_out",
            "unit",
            "warehouse",
            "bin_location",
            "reference_id",
            "remarks",
        ]
        read_only_fields = ["id"]


class ProductionSummarySerializer(serializers.ModelSerializer):
    """Serializer for Production Summary"""

    class Meta:
        model = ProductionSummary
        fields = [
            "id",
            "total_raw_material_cost",
            "total_other_cost",
            "total_production_cost",
            "total_input_quantity",
            "total_output_quantity",
            "total_waste_quantity",
            "yield_percentage",
            "cost_per_unit",
            "is_finalized",
        ]
        read_only_fields = ["id"]


class ProductionOrderListSerializer(serializers.ModelSerializer):
    """Serializer for Production Order List view"""

    class Meta:
        model = ProductionOrder
        fields = [
            "id",
            "production_id",
            "status",
            "production_for",
            "production_type",
            "batch_number",
            "production_date",
            "total_quantity",
            "total_cost",
            "created_at",
        ]
        read_only_fields = ["id"]


class ProductionOrderMaterialPlanSerializer(serializers.ModelSerializer):
    bom_variant_code = serializers.CharField(source="bom_variant.variant_code", read_only=True, default=None)
    source_label = serializers.CharField(source="get_source_type_display", read_only=True)

    class Meta:
        model = ProductionOrderMaterialPlan
        fields = [
            "id",
            "sequence",
            "source_type",
            "source_label",
            "is_bom_derived",
            "is_manual",
            "bom_variant",
            "bom_variant_code",
            "bom_component",
            "item",
            "product_subtype",
            "item_code",
            "item_name",
            "unit",
            "per_unit_quantity",
            "bom_quantity",
            "required_quantity",
            "received_quantity",
            "remaining_quantity",
            "request_quantity",
            "rate",
            "amount",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "bom_variant_code", "source_label"]


class ProductionOrderDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Production Order with nested data"""

    material_movements = MaterialMovementSerializer(many=True, read_only=True)
    material_plans = ProductionOrderMaterialPlanSerializer(many=True, read_only=True)
    transactions = ProductionTransactionSerializer(many=True, read_only=True)
    summary = ProductionSummarySerializer(read_only=True)
    cost_per_unit = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = ProductionOrder
        fields = [
            "id",
            "production_id",
            "production_for",
            "production_type",
            "status",
            "batch_number",
            "batch_date",
            "production_date",
            "shift",
            "plan_id",
            "planned_quantity",
            "planned_weight",
            "line_number",
            "line_name",
            "total_quantity",
            "other_cost",
            "material_cost",
            "total_cost",
            "start_date_time",
            "end_date_time",
            "extra_form_data",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "material_movements",
            "material_plans",
            "transactions",
            "summary",
            "cost_per_unit",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductionOrderCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating Production Orders"""
    STAGE_PRODUCTION_TYPES = {
        "WPE Additive Production",
        "WPE Blend Production",
        "WPE Granulated Blend Production",
        "WPE Production Line",
    }
    production_type = serializers.CharField()
    materials = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)
    extra_form_data = serializers.JSONField(required=False)

    class Meta:
        model = ProductionOrder
        fields = [
            "production_id",
            "production_for",
            "production_type",
            "status",
            "batch_number",
            "batch_date",
            "production_date",
            "shift",
            "plan_id",
            "planned_quantity",
            "planned_weight",
            "line_number",
            "line_name",
            "total_quantity",
            "other_cost",
            "material_cost",
            "total_cost",
            "start_date_time",
            "end_date_time",
            "extra_form_data",
            "materials",
        ]

    def validate(self, data):
        """Custom validation"""
        if data.get("end_date_time") and data.get("start_date_time"):
            if data["end_date_time"] < data["start_date_time"]:
                raise serializers.ValidationError(
                    {"end_date_time": "End time must be after start time."}
                )

        incoming_extra_form_data = dict(data.get("extra_form_data") or {})
        # New forms no longer manage inter-stage PRD linkage. Preserve existing historical
        # values on old records by ignoring new source-link writes instead of deleting data.
        incoming_extra_form_data.pop("source_order_id", None)
        incoming_extra_form_data.pop("source_production_id", None)
        incoming_extra_form_data.pop("source_stage", None)

        extra_form_data = dict(getattr(self.instance, "extra_form_data", {}) or {})
        extra_form_data.update(incoming_extra_form_data)
        data["extra_form_data"] = extra_form_data
        return data

    def validate_production_type(self, value):
        normalized = str(value).strip()
        if not normalized:
            raise serializers.ValidationError("Production type is required.")

        current_value = getattr(self.instance, "production_type", "")
        if current_value and current_value.strip().casefold() == normalized.casefold():
            return current_value

        legacy_values = {choice for choice, _ in ProductionOrder.PRODUCTION_TYPE_CHOICES}
        if normalized in legacy_values:
            return normalized

        if normalized in self.STAGE_PRODUCTION_TYPES:
            return normalized

        master_name = (
            ProductionTypeMaster.objects.filter(name__iexact=normalized, is_active=True)
            .values_list("name", flat=True)
            .first()
        )
        if master_name:
            return master_name

        raise serializers.ValidationError(
            "Select an active Production Type from Inventory & Store Masters."
        )

    def create(self, validated_data):
        materials = validated_data.pop("materials", [])
        materials = self._apply_pr_line_connection_defaults(validated_data, materials)
        order = super().create(validated_data)
        self._save_materials(order, materials)
        return order

    def update(self, instance, validated_data):
        materials = validated_data.pop("materials", None)
        order = super().update(instance, validated_data)
        if materials is not None:
            order.material_plans.all().delete()
            self._save_materials(order, materials)
        return order

    def _save_materials(self, order: ProductionOrder, materials):
        rows = []
        for index, material in enumerate(materials or [], start=1):
            rows.append(
                ProductionOrderMaterialPlan(
                    production_order=order,
                    sequence=int(material.get("sequence") or index),
                    source_type=material.get("source_type") or ProductionOrderMaterialPlan.SourceType.ITEM,
                    is_bom_derived=bool(material.get("is_bom_derived", False)),
                    is_manual=bool(material.get("is_manual", False)),
                    bom_variant_id=material.get("bom_variant"),
                    bom_component_id=material.get("bom_component"),
                    item_id=material.get("item"),
                    product_subtype_id=material.get("product_subtype"),
                    item_code=str(material.get("item_code") or ""),
                    item_name=str(material.get("item_name") or ""),
                    unit=str(material.get("unit") or "g"),
                    per_unit_quantity=material.get("per_unit_quantity") or 0,
                    bom_quantity=material.get("bom_quantity") or 0,
                    required_quantity=material.get("required_quantity") or 0,
                    received_quantity=material.get("received_quantity") or 0,
                    remaining_quantity=material.get("remaining_quantity") or 0,
                    request_quantity=material.get("request_quantity") or 0,
                    rate=material.get("rate") or 0,
                    amount=material.get("amount") or 0,
                    notes=str(material.get("notes") or ""),
                )
            )

        if rows:
            ProductionOrderMaterialPlan.objects.bulk_create(rows)

    def _is_pr_order(self, validated_data) -> bool:
        extra = validated_data.get("extra_form_data") or {}
        stage = str(extra.get("stage") or "").strip().upper()
        production_type = str(validated_data.get("production_type") or "").strip()
        return stage == "PR" or production_type == "WPE Production Line"

    def _parse_machine_id(self, raw_value) -> int | None:
        try:
            parsed = int(str(raw_value or "").strip())
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _recalculate_materials_for_quantity(self, materials, planned_quantity: Decimal, bom_multiplier: Decimal):
        recalculated = []
        for material in materials or []:
            payload = dict(material)
            per_unit_quantity = Decimal(str(payload.get("per_unit_quantity") or "0"))
            received_quantity = Decimal(str(payload.get("received_quantity") or "0"))
            rate = Decimal(str(payload.get("rate") or "0"))
            required_quantity = per_unit_quantity * planned_quantity * bom_multiplier
            remaining_quantity = required_quantity - received_quantity
            if remaining_quantity < Decimal("0"):
                remaining_quantity = Decimal("0")
            amount = required_quantity * rate

            payload["bom_quantity"] = f"{required_quantity:.3f}"
            payload["required_quantity"] = f"{required_quantity:.3f}"
            payload["remaining_quantity"] = f"{remaining_quantity:.3f}"
            payload["amount"] = f"{amount:.2f}"
            recalculated.append(payload)
        return recalculated

    def _apply_pr_line_connection_defaults(self, validated_data, materials):
        if not self._is_pr_order(validated_data):
            return materials

        extra_form_data = dict(validated_data.get("extra_form_data") or {})
        machine_id = self._parse_machine_id(extra_form_data.get("line_machine_id"))
        machine_code = str(validated_data.get("line_number") or "").strip()
        machine_name = str(validated_data.get("line_name") or "").strip()

        machine = resolve_production_machine(
            machine_id=machine_id,
            machine_code=machine_code,
            machine_name=machine_name,
        )
        if machine is None:
            return materials

        connection = get_active_line_connection_for_machine(
            machine_id=machine.id,
            machine_code=machine.machine_code,
            machine_name=machine.name,
            for_update=False,
        )
        if connection is None:
            extra_form_data["line_machine_id"] = str(machine.id)
            validated_data["extra_form_data"] = extra_form_data
            return materials

        available_weight = Decimal(
            str(
                getattr(connection.source_inventory_transaction, "balance_qty", None)
                or getattr(connection, "weight_kg", None)
                or "0.000"
            )
        )
        if available_weight <= Decimal("0"):
            extra_form_data["line_machine_id"] = str(machine.id)
            validated_data["extra_form_data"] = extra_form_data
            return materials

        validated_data["line_name"] = machine.name
        validated_data["line_number"] = machine.machine_code
        validated_data["planned_quantity"] = available_weight
        validated_data["planned_weight"] = available_weight

        extra_form_data["line_machine_id"] = str(machine.id)
        extra_form_data["line_connection_id"] = connection.id
        extra_form_data["line_connection_scan_code"] = connection.scan_code
        extra_form_data["line_connection_baglot"] = connection.serial_no
        extra_form_data["line_connection_weight_kg"] = f"{available_weight:.3f}"
        extra_form_data["line_connection_line_id"] = connection.production_line_id
        extra_form_data["line_connection_line_name"] = connection.production_line_name
        validated_data["extra_form_data"] = extra_form_data

        bom_multiplier = Decimal(str(extra_form_data.get("bom_multiplier") or "1"))
        validated_data["material_cost"] = Decimal(
            str(validated_data.get("material_cost") or "0.00")
        )
        recalculated_materials = self._recalculate_materials_for_quantity(materials, available_weight, bom_multiplier)
        total_material_cost = sum(Decimal(str(row.get("amount") or "0.00")) for row in recalculated_materials)
        validated_data["material_cost"] = total_material_cost
        validated_data["total_cost"] = total_material_cost + Decimal(str(validated_data.get("other_cost") or "0.00"))
        return recalculated_materials

# ===== RECIPE / BOM AND PRODUCTION MASTER SERIALIZERS =====


class ProductionCodeMasterSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ("id", "code", "name", "description", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "code", "created_at", "updated_at")


class ProductionMachineSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="machine_code", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta:
        model = ProductionMachine
        fields = (
            "id",
            "code",
            "machine_code",
            "name",
            "machine_type",
            "applicable_stages",
            "department",
            "department_name",
            "capacity",
            "capacity_uom",
            "serial_no",
            "manufacturer",
            "status",
            "is_active",
            "location",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "code", "machine_code", "created_at", "updated_at")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("name") and not getattr(self.instance, "name", ""):
            raise serializers.ValidationError({"name": "Machine name is required."})
        if not attrs.get("machine_type") and not getattr(self.instance, "machine_type", ""):
            raise serializers.ValidationError({"machine_type": "Machine type is required."})
        if not attrs.get("serial_no") and not getattr(self.instance, "serial_no", ""):
            raise serializers.ValidationError({"serial_no": "Machine serial is required."})
        return attrs


class ProfileSizeMasterSerializer(ProductionCodeMasterSerializer):
    class Meta(ProductionCodeMasterSerializer.Meta):
        model = ProfileSizeMaster
        fields = ProductionCodeMasterSerializer.Meta.fields + ("width", "thickness", "length", "uom")


class ColorCreationMasterSerializer(ProductionCodeMasterSerializer):
    class Meta(ProductionCodeMasterSerializer.Meta):
        model = ColorCreationMaster
        fields = ProductionCodeMasterSerializer.Meta.fields + ("color_group",)


class WorkCentreCreationMasterSerializer(ProductionCodeMasterSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta(ProductionCodeMasterSerializer.Meta):
        model = WorkCentreCreationMaster
        fields = ProductionCodeMasterSerializer.Meta.fields + ("department", "department_name", "capacity")


class PackingTypeMasterSerializer(ProductionCodeMasterSerializer):
    class Meta(ProductionCodeMasterSerializer.Meta):
        model = PackingTypeMaster
        fields = ProductionCodeMasterSerializer.Meta.fields + ("standard_pcs", "standard_weight", "uom")


class ProfileCreationMasterSerializer(ProductionCodeMasterSerializer):
    profile_type_name = serializers.CharField(source="profile_type.name", read_only=True)
    profile_size_name = serializers.CharField(source="profile_size.name", read_only=True)
    color_name = serializers.CharField(source="color.name", read_only=True)
    packing_type_name = serializers.CharField(source="packing_type.name", read_only=True, default=None)
    image_url = serializers.SerializerMethodField()

    class Meta(ProductionCodeMasterSerializer.Meta):
        model = ProfileCreationMaster
        fields = ProductionCodeMasterSerializer.Meta.fields + (
            "profile_type",
            "profile_type_name",
            "profile_size",
            "profile_size_name",
            "color",
            "color_name",
            "length",
            "weight_per_piece",
            "uom",
            "packing_type",
            "packing_type_name",
            "image",
            "image_url",
        )
        read_only_fields = ProductionCodeMasterSerializer.Meta.read_only_fields + ("image_url",)

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


class ProductionLineMasterSerializer(ProductionCodeMasterSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    machine_name = serializers.CharField(source="machine.name", read_only=True, default=None)
    machine_code = serializers.CharField(source="machine.machine_code", read_only=True, default=None)

    class Meta(ProductionCodeMasterSerializer.Meta):
        model = ProductionLineMaster
        fields = ProductionCodeMasterSerializer.Meta.fields + (
            "department",
            "department_name",
            "machine",
            "machine_name",
            "machine_code",
            "line_capacity",
            "capacity_uom",
            "status",
        )


class ProductionLineConnectionSerializer(serializers.ModelSerializer):
    production_line = serializers.IntegerField(source="production_line_id", read_only=True)
    production_line_code = serializers.SerializerMethodField()
    machine = serializers.IntegerField(source="machine_id", read_only=True, allow_null=True)
    machine_code = serializers.SerializerMethodField()
    production_order = serializers.IntegerField(source="production_order_id", read_only=True, allow_null=True)
    production_id = serializers.SerializerMethodField()
    bag = serializers.SerializerMethodField()
    bag_code = serializers.SerializerMethodField()
    connected_by = serializers.IntegerField(source="connected_by_id", read_only=True, allow_null=True)
    connected_by_name = serializers.SerializerMethodField()
    disconnected_by = serializers.IntegerField(source="disconnected_by_id", read_only=True, allow_null=True)
    disconnected_by_name = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    class Meta:
        model = ProductionLineConnection
        fields = (
            "id",
            "production_line",
            "production_line_name",
            "production_line_code",
            "machine",
            "machine_name",
            "machine_code",
            "scan_code",
            "item_code",
            "item_name",
            "reference_no",
            "serial_no",
            "weight_kg",
            "status",
            "connected_at",
            "disconnected_at",
            "duration",
            "production_order",
            "production_id",
            "bag",
            "bag_code",
            "connected_by",
            "connected_by_name",
            "disconnected_by",
            "disconnected_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def _get_user_name(self, user) -> str | None:
        if user is None:
            return None
        for accessor in ("get_full_name", "get_username"):
            if hasattr(user, accessor):
                value = getattr(user, accessor)()
                if str(value or "").strip():
                    return str(value).strip()
        for attr in ("username", "email"):
            value = getattr(user, attr, "")
            if str(value or "").strip():
                return str(value).strip()
        return str(user)

    def get_connected_by_name(self, obj):
        return self._get_user_name(obj.connected_by)

    def get_disconnected_by_name(self, obj):
        return self._get_user_name(obj.disconnected_by)

    def get_bag(self, obj):
        return None

    def get_bag_code(self, obj):
        return str(obj.serial_no or "").strip() or None

    def get_production_line_code(self, obj):
        return str(getattr(obj.production_line, "code", "") or "").strip() or None

    def get_machine_code(self, obj):
        if getattr(obj, "machine_id", None):
            return str(getattr(obj.machine, "machine_code", "") or "").strip() or None
        if getattr(obj.production_line, "machine_id", None):
            return str(getattr(obj.production_line.machine, "machine_code", "") or "").strip() or None
        return None

    def get_production_id(self, obj):
        for order in (obj.production_order, getattr(obj, "source_production_order", None)):
            value = str(getattr(order, "production_id", "") or "").strip()
            if value:
                return value
        return None

    def get_duration(self, obj):
        start = obj.connected_at
        end = obj.disconnected_at or timezone.now()
        if start is None or end is None or end < start:
            return None
        total_seconds = int((end - start).total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class GlScancodeDetailsSerializer(serializers.Serializer):
    scan_code = serializers.CharField()
    serial_no = serializers.CharField()
    reference_no = serializers.CharField(allow_blank=True, allow_null=True)
    item_code = serializers.CharField(allow_blank=True)
    item_name = serializers.CharField(allow_blank=True)
    weight_kg = serializers.DecimalField(max_digits=14, decimal_places=3)
    production_id = serializers.CharField(allow_blank=True, allow_null=True)
    is_connected = serializers.BooleanField()
    active_connection = ProductionLineConnectionSerializer(allow_null=True)


class ProductionLineConnectionConnectSerializer(serializers.Serializer):
    scan_code = serializers.CharField()
    production_line = serializers.IntegerField(required=False)
    production_line_id = serializers.IntegerField(required=False)
    production_order = serializers.IntegerField(required=False, allow_null=True)
    production_order_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        production_line_id = attrs.get("production_line") or attrs.get("production_line_id")
        if not production_line_id:
            raise serializers.ValidationError({"production_line": "production_line is required."})
        attrs["production_line_id"] = production_line_id
        attrs["production_order_id"] = attrs.get("production_order") or attrs.get("production_order_id")
        attrs["scan_code"] = str(attrs.get("scan_code") or "").strip()
        if not attrs["scan_code"]:
            raise serializers.ValidationError({"scan_code": "scan_code is required."})
        return attrs


class BinCreationMasterSerializer(ProductionCodeMasterSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta(ProductionCodeMasterSerializer.Meta):
        model = BinCreationMaster
        fields = ProductionCodeMasterSerializer.Meta.fields + (
            "department",
            "department_name",
            "capacity",
            "capacity_uom",
            "current_status",
            "current_material",
        )


class BagCreationMasterSerializer(ProductionCodeMasterSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)

    class Meta(ProductionCodeMasterSerializer.Meta):
        model = BagCreationMaster
        fields = ProductionCodeMasterSerializer.Meta.fields + (
            "standard_weight",
            "uom",
            "department",
            "department_name",
            "current_status",
        )


class PackingMaterialMasterSerializer(ProductionCodeMasterSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)

    class Meta(ProductionCodeMasterSerializer.Meta):
        model = PackingMaterialMaster
        fields = ProductionCodeMasterSerializer.Meta.fields + (
            "item",
            "item_name",
            "item_code",
            "uom",
            "standard_consumption",
        )


class BOMVariantComponentSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="component_code", read_only=True)
    item_name = serializers.CharField(source="component_name", read_only=True)
    category = serializers.CharField(source="component_category_name", read_only=True)
    source_type = serializers.ReadOnlyField()
    source_active = serializers.BooleanField(source="component_is_active", read_only=True, allow_null=True)

    class Meta:
        model = BOMVariantComponent
        fields = (
            "id",
            "item",
            "product_subtype",
            "source_type",
            "item_code",
            "item_name",
            "category",
            "is_active",
            "source_active",
            "target_weight_grams",
            "min_weight_grams",
            "max_weight_grams",
            "sequence",
            "is_regrind",
            "unit",
        )


class BOMVariantListSerializer(serializers.ModelSerializer):
    product_item_name = serializers.CharField(source="product_item.item_name", read_only=True, default=None)
    component_count = serializers.IntegerField(read_only=True, default=0)
    has_password = serializers.ReadOnlyField()
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = BOMVariant
        fields = (
            "id",
            "variant_code",
            "name",
            "product_item",
            "product_item_name",
            "revision",
            "batch_size",
            "batch_uom",
            "status",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "is_active",
            "notes",
            "component_count",
            "has_password",
            "created_at",
            "updated_at",
        )

    def get_approved_by_name(self, obj):
        return getattr(obj.approved_by, "username", None)


class BOMVariantDetailSerializer(serializers.ModelSerializer):
    product_item_name = serializers.CharField(source="product_item.item_name", read_only=True, default=None)
    components = BOMVariantComponentSerializer(many=True, read_only=True)
    has_password = serializers.ReadOnlyField()
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = BOMVariant
        fields = (
            "id",
            "variant_code",
            "name",
            "product_item",
            "product_item_name",
            "revision",
            "batch_size",
            "batch_uom",
            "status",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "is_active",
            "notes",
            "components",
            "has_password",
            "created_at",
            "updated_at",
        )

    def get_approved_by_name(self, obj):
        return getattr(obj.approved_by, "username", None)


class RecipeMasterSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="variant_code", read_only=True)
    description = serializers.CharField(source="notes", required=False, allow_blank=True)
    recipe_version = serializers.CharField(source="revision", required=False, allow_blank=True)
    approved_by_name = serializers.SerializerMethodField()
    component_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = BOMVariant
        fields = (
            "id",
            "code",
            "name",
            "description",
            "recipe_version",
            "batch_size",
            "batch_uom",
            "status",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "is_active",
            "component_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "code", "approved_by_name", "component_count", "created_at", "updated_at")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs["revision"] = str(attrs.get("revision") or "").strip() or "v1"
        attrs["notes"] = str(attrs.get("notes") or "").strip()
        return attrs

    def get_approved_by_name(self, obj):
        return getattr(obj.approved_by, "username", None)


class RecipeMasterDetailSerializer(RecipeMasterSerializer):
    components = BOMVariantComponentSerializer(many=True, read_only=True)

    class Meta(RecipeMasterSerializer.Meta):
        fields = RecipeMasterSerializer.Meta.fields + ("components",)


class BOMCreationMasterSerializer(ProductionCodeMasterSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)
    product_code = serializers.CharField(source="product.code", read_only=True, default=None)

    class Meta(ProductionCodeMasterSerializer.Meta):
        model = BOMCreationMaster
        fields = ProductionCodeMasterSerializer.Meta.fields + (
            "product",
            "product_name",
            "product_code",
            "bom_version",
            "output_quantity",
            "output_uom",
            "status",
        )


class BOMItemCreationMasterSerializer(serializers.ModelSerializer):
    bom_name = serializers.CharField(source="bom.name", read_only=True)
    bom_code = serializers.CharField(source="bom.code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)

    class Meta:
        model = BOMItemCreationMaster
        fields = (
            "id",
            "bom",
            "bom_name",
            "bom_code",
            "item",
            "item_name",
            "item_code",
            "item_type",
            "required_quantity",
            "uom",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "bom_name", "bom_code", "item_name", "item_code", "created_at", "updated_at")


class BatchWeightEntrySerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="component_code", read_only=True)
    item_name = serializers.CharField(source="component_name", read_only=True)
    category = serializers.CharField(source="component_category_name", read_only=True)
    source_type = serializers.CharField(source="bom_component.source_type", read_only=True)
    min_weight_grams = serializers.DecimalField(source="bom_component.min_weight_grams", max_digits=10, decimal_places=3, read_only=True)
    max_weight_grams = serializers.DecimalField(source="bom_component.max_weight_grams", max_digits=10, decimal_places=3, read_only=True)
    entered_by_username = serializers.CharField(source="entered_by.username", read_only=True, default=None)

    class Meta:
        model = BatchWeightEntry
        fields = ("id", "batch", "bom_component", "item", "item_code", "item_name", "category", "source_type",
                  "target_weight_grams", "min_weight_grams", "max_weight_grams",
                  "entered_weight_grams", "is_valid", "validation_notes", "source",
                  "entered_by", "entered_by_username", "entered_at")
        read_only_fields = ("id", "is_valid", "validation_notes", "entered_by", "entered_at", "batch", "item", "target_weight_grams")


class RegrindMaterialEntrySerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    added_by_username = serializers.CharField(source="added_by.username", read_only=True, default=None)

    class Meta:
        model = RegrindMaterialEntry
        fields = ("id", "production_order", "batch", "stage", "item", "item_code", "item_name",
                  "quantity_grams", "source_lot_no", "is_valid", "validation_notes", "notes",
                  "added_by", "added_by_username", "added_at")
        read_only_fields = ("id", "is_valid", "validation_notes", "added_by", "added_at", "production_order")


class ProductionBatchSerializer(serializers.ModelSerializer):
    weight_entries = BatchWeightEntrySerializer(many=True, read_only=True)
    regrind_entries = RegrindMaterialEntrySerializer(many=True, read_only=True)
    machine_name = serializers.CharField(source="machine.name", read_only=True, default=None)
    bom_variant_code = serializers.CharField(source="bom_variant.variant_code", read_only=True, default=None)
    bom_variant_name = serializers.CharField(source="bom_variant.name", read_only=True, default=None)
    operator_username = serializers.CharField(source="operator.username", read_only=True, default=None)
    display_batch_no = serializers.SerializerMethodField()
    display_status = serializers.SerializerMethodField()
    total_weight_grams = serializers.SerializerMethodField()
    all_weights_valid = serializers.SerializerMethodField()

    NEXT_STAGE_BY_STAGE = {
        ProductionBatch.Stage.AD: ProductionBatch.Stage.BL,
        ProductionBatch.Stage.BL: ProductionBatch.Stage.GL,
        ProductionBatch.Stage.GL: ProductionBatch.Stage.PR,
        ProductionBatch.Stage.PR: "COMPLETED",
    }
    STAGE_STATUS_LABELS = {
        ProductionBatch.Stage.BL: "BL - Blending",
        ProductionBatch.Stage.GL: "GL - Granulation",
        ProductionBatch.Stage.PR: "PR - Production",
    }
    STAGE_STATUS_ORDER = {
        ProductionBatch.Stage.AD: 0,
        ProductionBatch.Stage.BL: 1,
        ProductionBatch.Stage.GL: 2,
        ProductionBatch.Stage.PR: 3,
    }

    class Meta:
        model = ProductionBatch
        fields = ("id", "batch_no", "display_batch_no", "display_status", "production_order", "bom_variant", "bom_variant_code", "bom_variant_name",
                  "stage", "machine", "machine_name", "status",
                  "started_at", "completed_at", "operator", "operator_username",
                  "notes", "total_weight_grams", "all_weights_valid",
                  "weight_entries", "regrind_entries", "created_at", "updated_at")
        read_only_fields = ("id", "batch_no", "created_at", "updated_at")

    def get_display_batch_no(self, obj):
        return str(obj.batch_no or "").strip() or resolve_workflow_batch_no(obj)

    def get_display_status(self, obj):
        return obj.status

    def get_total_weight_grams(self, obj):
        entries = obj.weight_entries.all()
        total = sum(float(e.entered_weight_grams) for e in entries if e.entered_weight_grams is not None)
        if total == 0:
            output_capture = getattr(obj, "output_capture", None)
            if output_capture is not None:
                return round(float(output_capture.weight_kg), 3)
        return round(total, 3)

    def get_all_weights_valid(self, obj):
        entries = list(obj.weight_entries.all())
        if not entries:
            return False
        return all(e.is_valid for e in entries)


class ProductionOutputCaptureSerializer(serializers.ModelSerializer):
    binlot = serializers.SerializerMethodField()
    source_batch_no = serializers.CharField(source="source_batch.batch_no", read_only=True)
    source_batch_display_batch_no = serializers.SerializerMethodField()
    source_batch_display_status = serializers.SerializerMethodField()
    is_outwarded = serializers.SerializerMethodField()
    component_columns = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()

    class Meta:
        model = ProductionOutputCapture
        fields = (
            "id",
            "production_order",
            "source_batch",
            "source_batch_no",
            "source_batch_display_batch_no",
            "source_batch_display_status",
            "sequence",
            "scancode_id",
            "recipe_no",
            "quantity_kg",
            "weight_kg",
            "binlot",
            "is_outwarded",
            "session_key",
            "device_id",
            "workstation_id",
            "bridge_client_id",
            "weight_source",
            "captured_at",
            "component_columns",
            "details",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    @staticmethod
    def _parse_positive_int(value):
        try:
            parsed = int(str(value or "").strip())
        except (TypeError, ValueError):
            return 0
        return parsed if parsed > 0 else 0

    def _resolve_pr_capture_baglot(self, obj):
        source_batch = getattr(obj, "source_batch", None)
        production_order = getattr(obj, "production_order", None)
        if source_batch is None or production_order is None:
            return str(obj.binlot or "").strip()

        extra = production_order.extra_form_data or {}

        connection_id = self._parse_positive_int(extra.get("line_connection_id"))
        if connection_id:
            connection = (
                ProductionLineConnection.objects.select_related("source_inventory_transaction__output_capture")
                .filter(pk=connection_id)
                .first()
            )
            if connection is not None:
                resolved_baglot = resolve_inventory_baglot(
                    getattr(connection, "source_inventory_transaction", None),
                    fallback=str(connection.serial_no or "").strip(),
                )
                if resolved_baglot:
                    return resolved_baglot

        scan_code = str(extra.get("line_connection_scan_code") or "").strip()
        if scan_code:
            connection_row = (
                ProductionInventoryTransaction.objects.select_related("output_capture")
                .filter(
                    stage=ProductionInventoryTransaction.Stage.CONNECTION_TO_LINE,
                    scan_code__iexact=scan_code,
                )
                .order_by("-updated_at", "-created_at", "-id")
                .first()
            )
            resolved_baglot = resolve_inventory_baglot(connection_row)
            if resolved_baglot:
                return resolved_baglot

        machine_filters = Q()
        machine_id = self._parse_positive_int(extra.get("line_machine_id"))
        if machine_id:
            machine_filters |= Q(machine_id=machine_id) | Q(production_line__machine_id=machine_id)

        line_number = str(getattr(production_order, "line_number", "") or "").strip()
        if line_number:
            machine_filters |= (
                Q(machine__machine_code__iexact=line_number)
                | Q(production_line__machine__machine_code__iexact=line_number)
            )

        line_name = str(getattr(production_order, "line_name", "") or "").strip()
        if line_name:
            machine_filters |= (
                Q(machine__name__iexact=line_name)
                | Q(machine_name__iexact=line_name)
                | Q(production_line__machine__name__iexact=line_name)
            )

        if machine_filters:
            historical_connection = (
                ProductionLineConnection.objects.select_related("source_inventory_transaction__output_capture")
                .filter(machine_filters, connected_at__lte=obj.captured_at)
                .filter(Q(disconnected_at__isnull=True) | Q(disconnected_at__gte=obj.captured_at))
                .order_by("-connected_at", "-id")
                .first()
            )
            if historical_connection is not None:
                resolved_baglot = resolve_inventory_baglot(
                    getattr(historical_connection, "source_inventory_transaction", None),
                    fallback=str(historical_connection.serial_no or "").strip(),
                )
                if resolved_baglot:
                    return resolved_baglot

        active_connection = get_active_line_connection_for_order(production_order, for_update=False)
        if active_connection is not None:
            resolved_baglot = resolve_inventory_baglot(
                getattr(active_connection, "source_inventory_transaction", None),
                fallback=str(active_connection.serial_no or "").strip(),
            )
            if resolved_baglot:
                return resolved_baglot

        saved_baglot = str(extra.get("line_connection_baglot") or "").strip()
        if saved_baglot:
            return saved_baglot

        return str(obj.binlot or "").strip()

    def get_binlot(self, obj):
        if obj.source_batch.stage == ProductionBatch.Stage.PR:
            return self._resolve_pr_capture_baglot(obj)
        return str(obj.binlot or "").strip()

    def get_source_batch_display_batch_no(self, obj):
        return resolve_workflow_batch_no(obj.source_batch)

    def get_source_batch_display_status(self, obj):
        serializer = ProductionBatchSerializer(context={"requested_stage": obj.source_batch.stage})
        return serializer.get_display_status(obj.source_batch)

    @staticmethod
    def _get_required_entries(obj: ProductionOutputCapture):
        entries = list(obj.source_batch.weight_entries.all())
        entries.sort(key=lambda entry: (getattr(entry.bom_component, "sequence", 0), entry.id))
        positive_entries = [entry for entry in entries if float(entry.target_weight_grams or 0) > 0]
        return positive_entries or entries

    def get_is_outwarded(self, obj):
        return (
            obj.source_batch.stage in {ProductionBatch.Stage.BL, ProductionBatch.Stage.GL, ProductionBatch.Stage.PR}
            and obj.source_batch.status == ProductionBatch.BatchStatus.COMPLETED
        )

    def get_component_columns(self, obj):
        if obj.source_batch.stage != ProductionBatch.Stage.AD:
            label = (
                "Bin Weight"
                if obj.source_batch.stage == ProductionBatch.Stage.BL
                else "Bag Weight"
                if obj.source_batch.stage == ProductionBatch.Stage.GL
                else "Line Weight"
            )
            return [
                {
                    "id": obj.source_batch_id,
                    "label": label,
                }
            ]

        return [
            {
                "id": entry.bom_component_id,
                "label": entry.component_name,
            }
            for entry in self._get_required_entries(obj)
        ]

    def get_details(self, obj):
        if obj.source_batch.stage != ProductionBatch.Stage.AD:
            label = (
                "Bin Weight"
                if obj.source_batch.stage == ProductionBatch.Stage.BL
                else "Bag Weight"
                if obj.source_batch.stage == ProductionBatch.Stage.GL
                else "Line Weight"
            )
            return [
                {
                    "component_id": obj.source_batch_id,
                    "item_code": obj.source_batch.batch_no or obj.production_order.production_id,
                    "item_name": label,
                    "weight_kg": f"{Decimal(obj.weight_kg or 0):.3f}",
                    "captured_at": obj.captured_at,
                }
            ]

        return [
            {
                "component_id": entry.bom_component_id,
                "item_code": entry.component_code,
                "item_name": entry.component_name,
                "weight_kg": f"{Decimal(entry.entered_weight_grams or 0):.3f}",
                "captured_at": entry.entered_at,
            }
            for entry in self._get_required_entries(obj)
        ]


class ProductionStageRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order_id = serializers.IntegerField()
    production_id = serializers.CharField()
    stage = serializers.CharField()
    production_type = serializers.CharField()
    batch_no = serializers.CharField(allow_blank=True, allow_null=True)
    display_batch_no = serializers.CharField(allow_blank=True, allow_null=True)
    batch_count = serializers.IntegerField()
    production_date = serializers.DateField()
    shift = serializers.CharField(allow_blank=True, allow_null=True)
    line_no = serializers.CharField()
    start_date_time = serializers.DateTimeField(allow_null=True)
    end_date_time = serializers.DateTimeField(allow_null=True)
    plan_id = serializers.CharField(allow_blank=True, allow_null=True)
    status = serializers.CharField()
    workflow_status = serializers.CharField()
