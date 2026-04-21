from rest_framework import serializers
from .models import Item


class ItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = Item
        fields = '__all__'

    def validate_item_code(self, value):
        if not value:
            raise serializers.ValidationError("Item code is mandatory")
        return value

    def validate(self, data):
        # Optional: prevent duplicate item_name under same category
        if Item.objects.filter(
            item_name=data.get('item_name'),
            category=data.get('category')
        ).exists():
            raise serializers.ValidationError("Duplicate item in same category")
        return data