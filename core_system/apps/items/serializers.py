from rest_framework import serializers

from .models import Item, ItemStockTransaction


ITEM_STOCK_WRITE_ONLY_FIELDS = {
    "quantity",
    "weight",
    "incoming_quantity",
    "date",
    "ref_id",
    "trans_type",
    "sale_type",
    "doc_id",
    "contact",
    "warehouse",
    "bin",
}


class ItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(read_only=True)
    current_stock = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    on_hand = serializers.DecimalField(source="current_stock", max_digits=14, decimal_places=3, read_only=True)

    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, required=False, write_only=True)
    weight = serializers.DecimalField(max_digits=14, decimal_places=3, required=False, write_only=True)
    incoming_quantity = serializers.DecimalField(max_digits=14, decimal_places=3, required=False, write_only=True)

    date = serializers.DateField(required=False, write_only=True)
    ref_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)
    trans_type = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)
    sale_type = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)
    doc_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)
    contact = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)
    warehouse = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)
    bin = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)

    class Meta:
        model = Item
        fields = "__all__"
        read_only_fields = ("item_code", "current_stock", "created_at", "updated_at")

    def validate(self, data):
        for field_name in ("opening_stock", "quantity", "weight", "incoming_quantity"):
            value = data.get(field_name)
            if value is not None and value < 0:
                raise serializers.ValidationError({field_name: "Stock quantity cannot be negative."})

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

        if self.instance is not None:
            duplicate_query = Item.objects.filter(
                item_name=data.get("item_name", self.instance.item_name),
                category=data.get("category", self.instance.category),
                group=data.get("group", self.instance.group),
                sub_group=data.get("sub_group", self.instance.sub_group),
                unit=data.get("unit", self.instance.unit),
            ).exclude(pk=self.instance.pk)

            if duplicate_query.exists():
                raise serializers.ValidationError(
                    "Duplicate item with the same name, category, group, sub group, and unit already exists."
                )

        return data

    def create(self, validated_data):
        for field_name in ITEM_STOCK_WRITE_ONLY_FIELDS:
            validated_data.pop(field_name, None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for field_name in ITEM_STOCK_WRITE_ONLY_FIELDS:
            validated_data.pop(field_name, None)
        return super().update(instance, validated_data)


class ItemStockMovementSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    ref_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    trans_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    sale_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    doc_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    contact = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    warehouse = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bin = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, required=False)
    weight = serializers.DecimalField(max_digits=14, decimal_places=3, required=False)
    inwards = serializers.DecimalField(max_digits=14, decimal_places=3, required=False)
    outwards = serializers.DecimalField(max_digits=14, decimal_places=3, required=False)

    def validate(self, attrs):
        movement_type = self.context.get("movement_type")
        amount_fields = ("quantity", "weight", "inwards") if movement_type == "inward" else (
            "quantity",
            "weight",
            "outwards",
        )

        quantity = None
        for field_name in amount_fields:
            value = attrs.get(field_name)
            if value is not None:
                quantity = value
                break

        if quantity is None:
            raise serializers.ValidationError(
                "Provide a positive stock quantity using quantity, weight, "
                f"or {'inwards' if movement_type == 'inward' else 'outwards'}."
            )

        if quantity <= 0:
            raise serializers.ValidationError("Stock quantity must be greater than zero.")

        attrs["movement_quantity"] = quantity
        return attrs


class ItemStockTransactionSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)

    class Meta:
        model = ItemStockTransaction
        fields = "__all__"
