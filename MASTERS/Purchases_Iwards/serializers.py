from rest_framework import serializers
from .models import GRN, QCR


class GRNSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRN
        fields = "__all__"

    def validate_grn_no(self, value):
        if not value:
            raise serializers.ValidationError("GRN Number is required")
        return value


class QCRSerializer(serializers.ModelSerializer):
    source_grn_data = GRNSerializer(source="source_grn", read_only=True)

    class Meta:
        model = QCR
        fields = "__all__"
