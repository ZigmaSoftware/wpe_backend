# Units - This file defines the serializers for the UnitMaster model in the purchase_master module of the MASTERS app, which is responsible for converting UnitMaster model instances to and from JSON format for API interactions. The UnitSerializer class inherits from ModelSerializer and specifies that all fields of the UnitMaster model should be included in the serialization process, allowing for easy handling of unit-related data in API requests and responses.
from rest_framework import serializers
from .models import ItemGroup, ItemMaster, ProductCreation, StandardBOM, StandardBOMItem, UnitMaster

class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitMaster
        fields = '__all__'


# Item_groups - This file defines the serializers for the ItemGroup model in the purchase_master module of the MASTERS app, which is responsible for converting ItemGroup model instances to and from JSON format for API interactions. The ItemGroupSerializer class inherits from ModelSerializer and specifies that all fields of the ItemGroup model should be included in the serialization process, allowing for easy handling of item group-related data in API requests and responses. Additionally, the validate method is implemented to ensure that both the group name and code are unique when creating or updating item group entries, providing validation logic to prevent duplicate entries in the database.
class ItemGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemGroup
        fields = '__all__'

    def validate(self, attrs):
        if ItemGroup.objects.filter(group_name=attrs.get('group_name')).exists():
            raise serializers.ValidationError("Group name already exists")

        if ItemGroup.objects.filter(code=attrs.get('code')).exists():
            raise serializers.ValidationError("Code already exists")

        return attrs


# Standard BOM - This file defines the serializers for the StandardBOM and StandardBOMItem models in the purchase_master module of the MASTERS app, which are responsible for converting model instances to and from JSON format for API interactions. The StandardBOMItemSerializer class includes additional fields to represent the related item's name and code for better readability in API responses, while the StandardBOMSerializer includes a nested representation of its related items and the product name. The CreateBOMSerializer class is a custom serializer that validates the input data for creating a new BOM, ensuring that the product ID exists and that each item in the list has the required fields and valid references to existing items in the database.
class StandardBOMItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    item_code = serializers.CharField(source='item.item_code', read_only=True)

    class Meta:
        model = StandardBOMItem
        fields = ['id', 'item', 'item_name', 'item_code', 'qty', 'unit', 'remarks', 'is_active']


class StandardBOMSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    items = StandardBOMItemSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = StandardBOM
        fields = ['id', 'product', 'product_name', 'items', 'created_at']


class CreateBOMSerializer(serializers.Serializer):
    """Serializer for creating BOM with validation"""
    product_id = serializers.IntegerField(required=True)
    items = serializers.ListField(
        child=serializers.DictField(),
        required=True
    )

    def validate_product_id(self, value):
        try:
            ProductCreation.objects.get(id=value)
        except ProductCreation.DoesNotExist:
            raise serializers.ValidationError("Product not found")
        return value

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required")
        
        for idx, item in enumerate(value):
            if 'item_id' not in item:
                raise serializers.ValidationError(f"Item {idx}: 'item_id' is required")
            if 'qty' not in item:
                raise serializers.ValidationError(f"Item {idx}: 'qty' is required")
            if 'unit' not in item:
                raise serializers.ValidationError(f"Item {idx}: 'unit' is required")
            
            try:
                ItemMaster.objects.get(id=item['item_id'])
            except ItemMaster.DoesNotExist:
                raise serializers.ValidationError(f"Item {idx}: Item with ID {item['item_id']} not found")
        
        return value


