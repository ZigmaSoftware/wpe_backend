from rest_framework import serializers

from apps.items.models import Item

from .models import StockRequest, StoreStock, StoreTransaction


class StoreStockSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    category = serializers.CharField(source="item.category", read_only=True)
    group = serializers.CharField(source="item.group", read_only=True)
    sub_group = serializers.CharField(source="item.sub_group", read_only=True)

    class Meta:
        model = StoreStock
        fields = (
            "id",
            "item",
            "item_code",
            "item_name",
            "category",
            "group",
            "sub_group",
            "unit",
            "quantity",
            "created_at",
            "updated_at",
        )


class StockRequestSerializer(serializers.ModelSerializer):
    item = serializers.PrimaryKeyRelatedField(read_only=True)
    item_id = serializers.PrimaryKeyRelatedField(source="item", queryset=Item.objects.all(), write_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    category = serializers.CharField(source="item.category", read_only=True)
    group = serializers.CharField(source="item.group", read_only=True)
    sub_group = serializers.CharField(source="item.sub_group", read_only=True)
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True)

    class Meta:
        model = StockRequest
        fields = (
            "id",
            "item",
            "item_id",
            "item_code",
            "item_name",
            "category",
            "group",
            "sub_group",
            "unit",
            "quantity",
            "request_type",
            "department",
            "requested_for_name",
            "request_reason",
            "status",
            "requested_by",
            "requested_by_username",
            "approved_by",
            "approved_by_username",
            "requested_at",
            "approved_at",
        )
        read_only_fields = (
            "status",
            "requested_by",
            "requested_at",
            "approved_by",
            "approved_at",
        )

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Stock quantity must be greater than zero.")
        return value


class StoreTransactionSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)

    class Meta:
        model = StoreTransaction
        fields = (
            "id",
            "item",
            "item_code",
            "item_name",
            "unit",
            "transaction_type",
            "quantity",
            "reference_id",
            "metadata",
            "created_at",
        )
