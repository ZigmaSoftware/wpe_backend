from rest_framework import serializers

from .models import BlendingStock


class BlendingStockSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)

    class Meta:
        model = BlendingStock
        fields = (
            "id",
            "item",
            "item_code",
            "item_name",
            "unit",
            "quantity",
            "created_at",
            "updated_at",
        )
