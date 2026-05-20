from rest_framework import serializers
from .models import (
    ProductionOrder,
    MaterialMovement,
    ProductionTransaction,
    ProductionSummary,
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
            "production_type",
            "batch_number",
            "production_date",
            "total_quantity",
            "total_cost",
            "created_at",
        ]
        read_only_fields = ["id"]


class ProductionOrderDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Production Order with nested data"""

    material_movements = MaterialMovementSerializer(many=True, read_only=True)
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
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "material_movements",
            "transactions",
            "summary",
            "cost_per_unit",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductionOrderCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating Production Orders"""

    class Meta:
        model = ProductionOrder
        fields = [
            "production_id",
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
        ]

    def validate(self, data):
        """Custom validation"""
        if data.get("end_date_time") and data.get("start_date_time"):
            if data["end_date_time"] < data["start_date_time"]:
                raise serializers.ValidationError(
                    {"end_date_time": "End time must be after start time."}
                )
        return data


# ===== NEW OIMS SERIALIZERS =====

from .models import ProductionMachine, BOMVariant, BOMVariantComponent, ProductionBatch, BatchWeightEntry, RegrindMaterialEntry


class ProductionMachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionMachine
        fields = ("id", "machine_code", "name", "machine_type", "applicable_stages", "is_active", "location", "notes", "created_at", "updated_at")


class BOMVariantComponentSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    category = serializers.CharField(source="item.category", read_only=True)

    class Meta:
        model = BOMVariantComponent
        fields = ("id", "item", "item_code", "item_name", "category", "target_weight_grams", "min_weight_grams", "max_weight_grams", "sequence", "is_regrind", "unit")


class BOMVariantListSerializer(serializers.ModelSerializer):
    product_item_name = serializers.CharField(source="product_item.item_name", read_only=True, default=None)
    component_count = serializers.SerializerMethodField()

    class Meta:
        model = BOMVariant
        fields = ("id", "variant_code", "name", "product_item", "product_item_name", "revision", "is_active", "notes", "component_count", "created_at", "updated_at")

    def get_component_count(self, obj):
        return obj.components.count()


class BOMVariantDetailSerializer(serializers.ModelSerializer):
    product_item_name = serializers.CharField(source="product_item.item_name", read_only=True, default=None)
    components = BOMVariantComponentSerializer(many=True, read_only=True)

    class Meta:
        model = BOMVariant
        fields = ("id", "variant_code", "name", "product_item", "product_item_name", "revision", "is_active", "notes", "components", "created_at", "updated_at")


class BatchWeightEntrySerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    min_weight_grams = serializers.DecimalField(source="bom_component.min_weight_grams", max_digits=10, decimal_places=3, read_only=True)
    max_weight_grams = serializers.DecimalField(source="bom_component.max_weight_grams", max_digits=10, decimal_places=3, read_only=True)
    entered_by_username = serializers.CharField(source="entered_by.username", read_only=True, default=None)

    class Meta:
        model = BatchWeightEntry
        fields = ("id", "batch", "bom_component", "item", "item_code", "item_name",
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
    total_weight_grams = serializers.SerializerMethodField()
    all_weights_valid = serializers.SerializerMethodField()

    class Meta:
        model = ProductionBatch
        fields = ("id", "batch_no", "production_order", "bom_variant", "bom_variant_code", "bom_variant_name",
                  "stage", "machine", "machine_name", "status",
                  "started_at", "completed_at", "operator", "operator_username",
                  "notes", "total_weight_grams", "all_weights_valid",
                  "weight_entries", "regrind_entries", "created_at", "updated_at")
        read_only_fields = ("id", "batch_no", "created_at", "updated_at")

    def get_total_weight_grams(self, obj):
        entries = obj.weight_entries.all()
        total = sum(float(e.entered_weight_grams) for e in entries if e.entered_weight_grams is not None)
        return round(total, 3)

    def get_all_weights_valid(self, obj):
        entries = list(obj.weight_entries.all())
        if not entries:
            return False
        return all(e.is_valid for e in entries)
