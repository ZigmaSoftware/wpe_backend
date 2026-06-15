from rest_framework import serializers

from apps.items.models import Item
from apps.store.serializers import StoreStockSerializer


class BlendingStockSerializer(StoreStockSerializer):
    department = serializers.SerializerMethodField()

    class Meta(StoreStockSerializer.Meta):
        fields = StoreStockSerializer.Meta.fields + ("department",)
        read_only_fields = fields

    def get_department(self, obj):
        return "BLENDING"


class BlendingAdditiveRequestSerializer(serializers.Serializer):
    item_id = serializers.PrimaryKeyRelatedField(
        source="item",
        queryset=Item.objects.filter(status=True),
        required=True,
        error_messages={
            "required": "Please select a store item.",
            "null": "Please select a store item.",
            "does_not_exist": "Selected store item was not found.",
            "incorrect_type": "Please select a valid store item.",
        },
    )
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    request_date = serializers.DateField(required=False)
    require_date = serializers.DateField(required=False, allow_null=True)
    require_time = serializers.TimeField(required=False, allow_null=True)
    requested_for_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    request_reason = serializers.CharField(required=False, allow_blank=True, default="")
    department = serializers.CharField(max_length=100, default="BLENDING", required=False)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def validate(self, attrs):
        item = attrs.get("item")
        quantity = attrs.get("quantity")

        if item is None or quantity is None:
            raise serializers.ValidationError({"detail": "item_id and quantity are required."})

        attrs["items"] = [{"item": item, "quantity": quantity}]
        return attrs
