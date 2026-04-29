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
        duplicate_query = Item.objects.filter(
            item_name=data.get('item_name'),
            category=data.get('category')
        )

        if self.instance is not None:
            duplicate_query = duplicate_query.exclude(pk=self.instance.pk)

        if duplicate_query.exists():
            raise serializers.ValidationError("Duplicate item in same category")
        return data
