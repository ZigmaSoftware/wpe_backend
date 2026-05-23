from rest_framework import serializers
from .models import PreSales, PresalesRequest, PresalesRequestItem, PresalesAuditLog


class PreSalesSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreSales
        fields = '__all__'


class PresalesRequestItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    category = serializers.CharField(source="item.category", read_only=True)
    unit_display = serializers.CharField(source="item.unit", read_only=True)

    class Meta:
        model = PresalesRequestItem
        fields = ("id", "item", "item_code", "item_name", "category", "quantity", "unit", "unit_display", "remarks", "created_at")


class PresalesRequestItemWriteSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value


class PresalesRequestSerializer(serializers.ModelSerializer):
    items = PresalesRequestItemSerializer(many=True, read_only=True)
    submitted_by_username = serializers.CharField(source="submitted_by.username", read_only=True, default=None)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True, default=None)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True, default=None)

    class Meta:
        model = PresalesRequest
        fields = (
            "id", "request_no", "request_date", "category", "request_person",
            "department", "required_reason", "customer_type", "customer_name",
            "remarks", "status", "items",
            "submitted_by", "submitted_by_username", "submitted_at",
            "approved_by", "approved_by_username", "approved_at", "approval_remarks",
            "sent_to_prod_at", "created_by", "created_by_username",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "request_no", "status", "submitted_by", "submitted_at",
            "approved_by", "approved_at", "sent_to_prod_at", "created_at", "updated_at",
        )


class PresalesRequestCreateSerializer(serializers.Serializer):
    request_date = serializers.DateField()
    category = serializers.ChoiceField(choices=PresalesRequest.Category.choices)
    request_person = serializers.CharField(max_length=255)
    department = serializers.CharField(max_length=100)
    required_reason = serializers.CharField(min_length=5)
    customer_type = serializers.CharField(max_length=50, default="ADDITIVE_MO", required=False)
    customer_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    remarks = serializers.CharField(required=False, allow_blank=True, default="")
    items = PresalesRequestItemWriteSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        item_ids = [v["item_id"] for v in value]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError("Duplicate items are not allowed.")
        return value


class PresalesAuditLogSerializer(serializers.ModelSerializer):
    performed_by_username = serializers.CharField(source="performed_by.username", read_only=True, default=None)

    class Meta:
        model = PresalesAuditLog
        fields = ("id", "action", "performed_by", "performed_by_username", "notes", "created_at")
