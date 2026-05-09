from __future__ import annotations

from rest_framework import serializers

from .models import Item


class ItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(read_only=True)
    opening_stock = serializers.DecimalField(max_digits=14, decimal_places=3, required=False, write_only=True)
    current_stock = serializers.DecimalField(max_digits=14, decimal_places=3, required=False, write_only=True)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, required=False, write_only=True)
    incoming_quantity = serializers.DecimalField(max_digits=14, decimal_places=3, required=False, write_only=True)
    weight = serializers.DecimalField(max_digits=14, decimal_places=3, required=False, write_only=True)

    class Meta:
        model = Item
        fields = (
            "id",
            "product_type",
            "category",
            "group",
            "sub_group",
            "item_name",
            "external_item_id",
            "item_code",
            "hsn_code",
            "unit",
            "product_details",
            "description",
            "min_max_status",
            "status",
            "opening_stock",
            "current_stock",
            "quantity",
            "incoming_quantity",
            "weight",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("item_code", "created_at", "updated_at")

    def validate(self, data):
        external_item_id = data.get("external_item_id")
        if external_item_id is not None:
            external_item_id = str(external_item_id).strip() or None
            data["external_item_id"] = external_item_id

            if external_item_id:
                duplicate_external_id_query = Item.objects.filter(external_item_id__iexact=external_item_id)
                if self.instance is not None:
                    duplicate_external_id_query = duplicate_external_id_query.exclude(pk=self.instance.pk)

                if duplicate_external_id_query.exists():
                    raise serializers.ValidationError(
                        {"external_item_id": "An item with this external item ID already exists."}
                    )

        duplicate_query = Item.objects.filter(
            item_name=data.get("item_name", getattr(self.instance, "item_name", None)),
            category=data.get("category", getattr(self.instance, "category", None)),
            group=data.get("group", getattr(self.instance, "group", None)),
            sub_group=data.get("sub_group", getattr(self.instance, "sub_group", None)),
            unit=data.get("unit", getattr(self.instance, "unit", None)),
        )
        if self.instance is not None:
            duplicate_query = duplicate_query.exclude(pk=self.instance.pk)

        if duplicate_query.exists():
            raise serializers.ValidationError(
                "Duplicate item with the same name, category, group, sub group, and unit already exists."
            )

        return data

    def create(self, validated_data):
        for field_name in ("opening_stock", "current_stock", "quantity", "incoming_quantity", "weight"):
            validated_data.pop(field_name, None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for field_name in ("opening_stock", "current_stock", "quantity", "incoming_quantity", "weight"):
            validated_data.pop(field_name, None)
        return super().update(instance, validated_data)
