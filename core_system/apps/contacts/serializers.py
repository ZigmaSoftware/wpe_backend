import re

from rest_framework import serializers

from .models import Contact


PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{9,14}$")
GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_PATTERN   = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Contact
        fields = "__all__"
        read_only_fields = ("ref_code", "created_at", "updated_at")

    def validate_phone(self, value):
        normalized = re.sub(r"[\s().-]+", "", value or "")
        if not PHONE_PATTERN.fullmatch(normalized):
            raise serializers.ValidationError("Enter a valid phone number (10–15 digits).")
        return normalized

    def validate_gstin(self, value):
        if not value:
            return value
        normalized = value.strip().upper()
        if not GSTIN_PATTERN.fullmatch(normalized):
            raise serializers.ValidationError("Enter a valid 15-character GSTIN.")
        return normalized

    def validate_pan(self, value):
        if not value:
            return value
        normalized = value.strip().upper()
        if not PAN_PATTERN.fullmatch(normalized):
            raise serializers.ValidationError("Enter a valid 10-character PAN (e.g. ABCDE1234F).")
        return normalized
