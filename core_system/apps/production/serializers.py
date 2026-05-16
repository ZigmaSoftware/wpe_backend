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
