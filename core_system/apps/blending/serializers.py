from rest_framework import serializers

from .models import DepartmentStock, StockTransfer


class DepartmentStockSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)

    class Meta:
        model = DepartmentStock
        fields = (
            "id",
            "item",
            "item_code",
            "item_name",
            "unit",
            "department",
            "quantity",
            "created_at",
            "updated_at",
        )


class StockTransferSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)

    class Meta:
        model = StockTransfer
        fields = (
            "id",
            "item",
            "item_code",
            "item_name",
            "from_department",
            "to_department",
            "quantity",
            "requested_at",
            "completed_at",
            "status",
        )


class StockTransferRequestSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Stock quantity must be greater than zero.")
        return value
