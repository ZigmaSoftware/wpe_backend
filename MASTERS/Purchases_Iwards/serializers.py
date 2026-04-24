from rest_framework import serializers
from .models import GRN


class GRNSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRN
        fields = "__all__"

    def validate_grn_no(self, value):
        if not value:
            raise serializers.ValidationError("GRN Number is required")
        return value