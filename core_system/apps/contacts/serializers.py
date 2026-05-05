import re

from rest_framework import serializers

from .models import Contact


PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{9,14}$")
GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = "__all__"
        read_only_fields = ("ref_code", "created_at", "updated_at")

    def validate_phone(self, value):
        normalized = re.sub(r"[\s().-]+", "", value or "")
        if not PHONE_PATTERN.fullmatch(normalized):
            raise serializers.ValidationError("Enter a valid phone number.")
        return normalized

    def validate_gstin(self, value):
        if not value:
            return value

        normalized = value.strip().upper()
        if not GSTIN_PATTERN.fullmatch(normalized):
            raise serializers.ValidationError("Enter a valid GSTIN.")
        return normalized

