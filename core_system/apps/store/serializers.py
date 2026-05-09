from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.items.models import Item, STOCK_ZERO

from .models import StockRequest, StockRequestItem, StoreStock, StoreTransaction, Warehouse


def serialize_quantity(value) -> str:
    decimal_value = value if value is not None else STOCK_ZERO
    return f"{decimal_value:.3f}"


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = (
            "id",
            "unique_id",
            "code",
            "name",
            "warehouse_type",
            "description",
            "is_active",
            "is_system",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class StoreStockSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    net_available_qty = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)

    class Meta:
        model = StoreStock
        fields = (
            "id",
            "item",
            "item_code",
            "item_name",
            "unit",
            "warehouse",
            "warehouse_code",
            "warehouse_name",
            "available_qty",
            "reserved_qty",
            "net_available_qty",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class StockRequestItemWriteSerializer(serializers.Serializer):
    item_id = serializers.PrimaryKeyRelatedField(source="item", queryset=Item.objects.filter(status=True))
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value


class StockRequestCreateSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    items = StockRequestItemWriteSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one store request item is required.")

        item_ids = [row["item"].id for row in value]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError("Duplicate items are not allowed in a single store request.")
        return value


class StockRequestItemReadSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    available_qty = serializers.SerializerMethodField()
    shortage_qty = serializers.SerializerMethodField()

    class Meta:
        model = StockRequestItem
        fields = (
            "id",
            "unique_id",
            "item",
            "item_code",
            "item_name",
            "unit",
            "requested_qty",
            "approved_qty",
            "issued_qty",
            "available_qty",
            "shortage_qty",
            "remarks",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_available_qty(self, obj):
        availability_map = self.context.get("availability_map", {})
        warehouse_id = getattr(obj.stock_request, "issuing_warehouse_id", None)
        return serialize_quantity(availability_map.get((warehouse_id, obj.item_id), STOCK_ZERO))

    def get_shortage_qty(self, obj):
        availability_map = self.context.get("availability_map", {})
        warehouse_id = getattr(obj.stock_request, "issuing_warehouse_id", None)
        available_qty = availability_map.get((warehouse_id, obj.item_id), STOCK_ZERO)
        shortage = obj.requested_qty - available_qty
        return serialize_quantity(shortage if shortage > STOCK_ZERO else STOCK_ZERO)


class StockRequestSerializer(serializers.ModelSerializer):
    items = StockRequestItemReadSerializer(many=True, read_only=True)
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)
    action_by_username = serializers.CharField(source="action_by.username", read_only=True)
    cancelled_by_username = serializers.CharField(source="cancelled_by.username", read_only=True)
    requesting_warehouse_code = serializers.CharField(source="requesting_warehouse.code", read_only=True)
    requesting_warehouse_name = serializers.CharField(source="requesting_warehouse.name", read_only=True)
    issuing_warehouse_code = serializers.CharField(source="issuing_warehouse.code", read_only=True)
    issuing_warehouse_name = serializers.CharField(source="issuing_warehouse.name", read_only=True)
    total_requested_qty = serializers.SerializerMethodField()
    total_approved_qty = serializers.SerializerMethodField()
    total_issued_qty = serializers.SerializerMethodField()

    class Meta:
        model = StockRequest
        fields = (
            "id",
            "request_no",
            "status",
            "requesting_warehouse",
            "requesting_warehouse_code",
            "requesting_warehouse_name",
            "issuing_warehouse",
            "issuing_warehouse_code",
            "issuing_warehouse_name",
            "remarks",
            "approval_remarks",
            "requested_by",
            "requested_by_username",
            "action_by",
            "action_by_username",
            "cancelled_by",
            "cancelled_by_username",
            "requested_at",
            "action_at",
            "cancelled_at",
            "total_requested_qty",
            "total_approved_qty",
            "total_issued_qty",
            "items",
        )
        read_only_fields = fields

    def get_total_requested_qty(self, obj):
        return serialize_quantity(sum((line.requested_qty for line in obj.items.all()), start=Decimal("0.000")))

    def get_total_approved_qty(self, obj):
        return serialize_quantity(sum((line.approved_qty for line in obj.items.all()), start=Decimal("0.000")))

    def get_total_issued_qty(self, obj):
        return serialize_quantity(sum((line.issued_qty for line in obj.items.all()), start=Decimal("0.000")))


class StockRequestApproveSerializer(serializers.Serializer):
    approval_remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class StockRequestRejectSerializer(serializers.Serializer):
    approval_remarks = serializers.CharField(required=True, allow_blank=False)


class StockRequestCancelSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class StoreTransactionSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = StoreTransaction
        fields = (
            "id",
            "transaction_no",
            "transaction_date",
            "transaction_type",
            "reference_type",
            "reference_id",
            "item",
            "item_code",
            "item_name",
            "unit",
            "warehouse",
            "warehouse_code",
            "warehouse_name",
            "inward_qty",
            "outward_qty",
            "balance_qty",
            "remarks",
            "metadata",
            "created_by",
            "created_by_username",
            "created_at",
        )
        read_only_fields = fields


class StockMovementSerializer(serializers.Serializer):
    item_id = serializers.PrimaryKeyRelatedField(source="item", queryset=Item.objects.filter(status=True))
    warehouse_id = serializers.PrimaryKeyRelatedField(source="warehouse", queryset=Warehouse.objects.filter(is_active=True))
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    transaction_type = serializers.ChoiceField(choices=StoreTransaction.TransactionType.choices)
    reference_type = serializers.ChoiceField(choices=StoreTransaction.ReferenceType.choices)
    reference_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    transaction_date = serializers.DateField(required=False)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value
