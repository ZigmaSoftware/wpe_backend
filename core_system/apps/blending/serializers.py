from rest_framework import serializers

from apps.items.models import Item

from .models import BlendingStock


class BlendingStockSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    category = serializers.CharField(source="item.category", read_only=True)
    group = serializers.CharField(source="item.group", read_only=True)
    sub_group = serializers.CharField(source="item.sub_group", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    department = serializers.SerializerMethodField()

    class Meta:
        model = BlendingStock
        fields = (
            "id",
            "item",
            "item_code",
            "item_name",
            "category",
            "group",
            "sub_group",
            "unit",
            "department",
            "quantity",
            "created_at",
            "updated_at",
        )

    def get_department(self, obj):
        return "BLENDING"


class BlendingAdditiveRequestSerializer(serializers.Serializer):
    item_id = serializers.PrimaryKeyRelatedField(source="item", queryset=Item.objects.all())
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    requested_for_name = serializers.CharField(max_length=255)
    request_reason = serializers.CharField()
    department = serializers.CharField(max_length=100, default="BLENDING")
